# -*- coding: utf-8 -*-
"""
Created on Tue May 17 17:03:41 2016

@author: Martin Friedl

Tool to read in a MBE recipe and visually display what it will do. Is meant to help the grower visualize what their recipe will do
"""

import re
import copy
import numpy as np
import pandas as pd
from NumericStringParser import NumericStringParser
nsp = NumericStringParser()

import matplotlib.pyplot as plt
import matplotlib as mpl
plt.ion()

def cmdDefine(command):
    """
    This function handles define statements in the MBE recipe file format. It takes a command, parses it and executes it.
    """
    if not(command.split(' ')[0].lower() == 'define'):
        raise ValueError("Define command didn't begin with 'Define'")
    command = " ".join(command.split(' ')[1:])
    command = command.split('=')
    command = [subcmd.strip() for subcmd in command]
    
    match = re.match(r"([0-9]+) ?([a-z]+)", command[-1], re.I) #Check if argument contains units
    if match:
        dictUnits = {'ms':0.001,'s':1.0,'min':60.0,'hours':60.0*60.0,'days':60.0*60.0*24.0}  
        items = match.groups()
        command.pop() #Remove last entry in command list
        command.extend(items) #Add parsed commands to command list
        command[1] = str(float(command[1])*dictUnits[command[-1]])
        command.pop() #Remove units at end
        
    return tuple(command)

def cmdShutter(command):
    """
    This function handles shutter commands, either open or close
    """
    shutterCommand = command.split(' ')[0].lower()
    if not(shutterCommand == 'open') and not(shutterCommand == 'close'):
            raise ValueError("Open/Close command didn't begin with 'Open' or 'Close'")           
    shutters = command.split(' ',1)[1]
    shutters = shutters.split(',')
    shutters = [shutter.strip() for shutter in shutters]
    return (shutters, shutterCommand=='open')

def cmdSet(command):
    if not(command.split(' ')[0].lower() == 'set'):
        raise ValueError("Define command didn't begin with 'Define'")    
    command = command.split(' ')[1:]
    return tuple(command)
    

def cmdWait(command):
    if not(command.split(' ')[0].lower() == 'wait'):
        raise ValueError("Wait command didn't begin with 'Wait'")
    command = [subCMD for subCMD in command.split(' ') if subCMD]    
    
    if command[0].lower() == 'wait' and command[1].lower() == 'until': #more complex "wait until"
        command = command[2:]
        if (command[0].find('$') == -1): command[0] = "${}$".format(command[0]) #pad variables with $$
        command = " ".join(command)
    elif command[0].lower() == 'wait': #Simple wait for X amount of time
        command = command[1]
        match = re.match(r"([0-9]+) ?([a-z]+)", command, re.I) #Check if argument contains units
        if match:
            dictUnits = {'ms':0.001,'s':1.0,'min':60.0,'hours':60.0*60.0,'days':60.0*60.0*24.0}  
            items = match.groups()
            command = str(float(items[0])*dictUnits[items[1]])
        command = "$Time$ > $waitStartTime$ + {}".format(command)
    else:
        raise ValueError("Wait command didn't begin with 'Wait' or 'Wait Until'")
    return command
                    
def cmdCalculate(command):
    if not(command.split(' ')[0].lower() == 'calculate'):
        raise ValueError("Calculate command didn't begin with 'Calculate'")    
    command = command.split(' ')[1:]
    command = "".join(command).split('=')
    return tuple(command)

def doTimeStep(variables,timeStep,what):
    difference = variables[what+'.PV.TSP'] - variables[what+'.PV']
    if np.abs(difference) > 0: #It is ramping
        increment = timeStep*variables[what+'.PV.Rate']/60.0*np.sign(difference)
        if np.abs(increment) < np.abs(difference): #Setpoint not reached
            variables[what+'.PV'] += increment
        else: #Setpoint reached
            variables[what+'.PV'] = variables[what+'.PV.TSP']
    return variables
      
def promptRecipeFile(filename = None, debug = False):
    '''Prompts user to input a logfile filename, then it tries to read the logfile and returns the data.
    
    Args: 
        filename (str): only used during debugging, function uses this filename if debug=True
        debug (bool): if True then takes the filename specified in the filename argument
    
    Yields: 
        log (LogFile): Logfile class of the specified filename
    '''
    while True:
        try:
            if debug: #Debug mode is on, takes filename specified in the code
                pass                        
            else:
                filename = raw_input('Please input the recipe file name (extension is optional, type "exit" to quit): \n')
            if filename.lower() == "exit": 
                exit() #Stop program
                break
            if filename[-4:]!='.txt': #Extension is optional
                filename = filename + '.txt'            
        except IOError: 
            print('Error - Could not load log file "{:s}". Please try again.'.format(filename))
            continue
        except SystemExit:
            print('Exiting...')
        return filename

class RecipeSimulation():
    '''
    Used for simulating recipes
    '''
    def __init__(self, recipename):
        self.timeStep = 1
        self.recipename = recipename
        # Initialize MBE variables
        self.dataArray = []
        self.variables = {}
        self.variables['Time'] = 0
        self.variables['Manip.PV'] = 200
        self.variables['Manip.RS.RPM'] = 0
        self.variables['Ga.PV'] = 550
        self.variables['Ga.PV.TSP'] = 550
        self.variables['Ga.PV.Rate'] = 30
        self.variables['In.PV'] = 515
        self.variables['In.PV.TSP'] = 515
        self.variables['In.PV.Rate'] = 15
        self.variables['As.PV'] = 374
        self.variables['As.PV.TSP'] = 374
        self.variables['As.PV.Rate'] = 30
        self.variables['AsCracker.PV'] = 600
        self.variables['AsCracker.PV.Rate'] = 2
        self.variables['Sb.PV'] = 250
        self.variables['Sb.PV.TSP'] = 250
        self.variables['Sb.PV.Rate'] = 5
        self.variables['SbCracker.PV'] = 800
        self.variables['SbCracker.PV.Rate'] = 10
        self.variables['Al.PV'] = 750
        self.variables['Al.PV.TSP'] = 750
        self.variables['Al.PV.Rate'] = 20
        self.variables['SUKO.OP'] = 30
        self.variables['Shutter.In'] = bool(False)
        self.variables['Shutter.Ga'] = False
        self.variables['Shutter.As'] = False
        self.variables['Shutter.Al'] = False
        self.variables['Shutter.Sb'] = False
        self.variables['Shutter.SUSI'] = False
        self.variables['Shutter.SUKO'] = False
        self.variables['Shutter.Pyrometer'] = False

        self.recipe = self.load_recipe(recipename)

    def load_recipe(self, recipename):
        '''
        Loads the recipe given as the recipename. Removes empty lines and comments.
        :param recipename: Link to filename of recipe that you want to parse
        :return: recipe as array of strings, line by line
        '''
        with open(recipename) as f:  # Load the recipe
            content = f.readlines()
        content = [line.strip() for line in content]  # Remove leading or trailing characters
        content = [line for line in content if line]  # Remove empty lines
        content = [line for line in content if line[0] != '#']  # Remove comment lines
        content = [line.split('#')[0].strip() for line in content]  # Remove comments at ends of lines
        return content

    def run_simulation(self):
        '''
        Starts the simulation of the recipe. Populating the DataArray variable
        :return: True if recipe ended successfully, false if recipe went into infinite loop
        '''
        # Loop through the recipe
        infiniteLoop = False
        for line in self.recipe:
            waiting = False
            commandType = line.split(' ')[0].lower()

            # Parse commands based on command type
            if commandType == 'define':
                key, value = cmdDefine(line)
                self.variables[key] = float(value)
            elif commandType == 'set':
                key, value = cmdSet(line)
                if not (value.find('$') == -1):  # Value is a variable
                    value = self.variables[value.replace('$', '')]
                self.variables[key] = float(value)
            elif commandType == 'open' or commandType == 'close':
                keys, value = cmdShutter(line)
                for key in keys:
                    self.variables['Shutter.' + key] = bool(value)
            elif commandType == 'wait':
                condition = cmdWait(line)
                operator = re.search(r'([<>]=?)', condition).groups(1)[0]
                waiting = True
                self.variables['waitStartTime'] = self.variables['Time']  # Start timer
            elif commandType == 'calculate':
                key, value = cmdCalculate(line)
                while not (value.find('$') == -1):  # Value is a variable
                    m = re.search(r"\$(\w+)\$", line)  # Find name of variable
                    varVal = self.variables[m.group(1)]  # Get value of variable
                    pos1 = value.find('$', 0)
                    pos2 = value.find('$', 1)
                    value = value[0:pos1] + str(varVal) + value[pos2 + 1:]  # Inject variable value
                self.variables[key] = float(nsp.eval(value))
            elif commandType == 'include': #TODO: implement indluce statements in recipe
                pass

            while waiting:
                # Evaluate the current wait condition
                expression = condition
                pos1 = 0
                while not (expression.find('$') == -1):  # There are still variables to replace
                    m = re.search(r"\$([\w.]+)\$", expression)  # Find name of variable
                    varVal = self.variables[m.group(1)]  # Get value of variable
                    pos1 = expression.find('$', pos1)
                    pos2 = expression.find('$', pos1 + 1)
                    expression = expression[:pos1] + str(varVal) + expression[
                                                                   pos2 + 1:]  # Inject variable value
                # Take a step in time
                self.variables['Time'] += self.timeStep
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'Manip')
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'Ga')
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'In')
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'As')
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'Sb')
                self.variables = self.doTimeStep(self.variables, self.timeStep, 'Al')
                # Save data to array
                self.dataArray.append(copy.deepcopy(self.variables))
                # Check if wait condition has been satisfied
                waiting = not (eval(expression))

                if self.variables['Time'] >= 12.0 * 60 * 60:
                    infiniteLoop = True
                    break

            if infiniteLoop: return True
        return False

    def doTimeStep(self, variables, timeStep, what):
        difference = variables[what + '.PV.TSP'] - variables[what + '.PV']
        if np.abs(difference) > 0:  # It is ramping
            increment = timeStep * variables[what + '.PV.Rate'] / 60.0 * np.sign(difference)
            if np.abs(increment) < np.abs(difference):  # Setpoint not reached
                variables[what + '.PV'] += increment
            else:  # Setpoint reached
                variables[what + '.PV'] = variables[what + '.PV.TSP']
        return variables

    def plot_recipe(self):
        if self.dataArray == []:
            print('Error: DataArray is empty, need to run the simulation first!')
            return False
        ax1 = plt.subplot(211)
        ax2 = plt.subplot(212, sharex=ax1)

        df = pd.DataFrame()
        df = df.from_dict(self.dataArray)
        df.loc[:, 'TimeInMins'] = df.loc[:, 'Time'] / 60.0
        # df.set_index('Time')

        df1 = df.filter(regex=".PV$")
        df1['TimeInMin'] = df1.index / 60.0
        df2 = df.filter(regex="^Shutter.")
        for i, col in enumerate(df2.columns):
            df2[col] = df2[col].apply(int) * (.9 + (i / 20.))
        df2['TimeInMin'] = df2.index / 60.0

        df1.plot(x='TimeInMin', ax=ax1, grid=True, ylim=[200, 1200])
        try:
            df2.plot.area(x='TimeInMin', ax=ax2, grid=True, ylim=[-0.1, 1.3], stacked=False, sharex=True)
        except(AttributeError):  # If installation doesn't have latest version of matplotlib don't use "area" attribute
            print('Warning: Detected old version of matplotlib, update for prettier plots!')
            df2.plot(x='TimeInMin', ax=ax2, grid=True, ylim=[-0.1, 1.3], sharex=True)

        # TODO: google how to put legend outside of the plot area
        # TODO: update to latest version of matplotlib
        # TODO: Figure out how to pass the recipe to be plotted directly when calling the function (easier)
        ax1.set_ylabel('Temperature ($^\circ$C)')
        ax2.set_xlabel('Time (min)')
        ax2.set_ylabel('Shutter Opening')

        return True

#Running as main function
if __name__ == '__main__':

    debug = False
    filename = 'D1-16-05-17-B.txt'
    
    if not(debug):    
        filename = promptRecipeFile(debug) 

    sim = RecipeSimulation(filename)
    inf_loop = sim.run_simulation()
    if inf_loop:
        print('Infinite Loop Detected! Aborted Recipe after 12 Hours.')

    print("Plotting recipe...")
    sim.plot_recipe()

    #Wait for user input before closing the program
    raw_input("Press Enter to continue...")
