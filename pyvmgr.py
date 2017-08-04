#!/usr/bin/env python3

import atexit
import sys
import time
import ssl
import datetime
import io
import os
import getpass

from pathlib import Path
from time import sleep
from pyVmomi import vim, vmodl
from pyVim.task import WaitForTask
from pyVim import connect
from cmd2 import Cmd

class Vsphere:
    """
        vSphere Object.
        self.vmsContainer is the view containing the VM.  New views could be added
    """

    def __init__(self, vCenterServer, vCenterUserName, vCenterPassword):

        vSphere = None
        context = None

        if hasattr(ssl, "_create_unverified_context"):
            context = ssl._create_unverified_context()

        vSphere = connect.Connect(vCenterServer, 443, vCenterUserName, vCenterPassword, sslContext=context)

        #Disconnects on program exit
        atexit.register(connect.Disconnect, vSphere)

        if not vSphere:
            raise Exception("Error connecting to vCenter Server")
        
        content = vSphere.RetrieveContent()

        self.vmsContainer = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)
    

    def getContainer(self):
        return self.vmsContainer


class Group:
    """
        List of VMs to manage at once.
        It can be loaded from a file, or from a comma separated string.
    """

    def __init__(self, vmsList, vmsContainer):
        self.vmsList = []
        for node in vmsList:
            self.addNode(node, vmsContainer)


    def __str__(self):
        vms = ""
        for node in self.vmsList:
            vms = vms + str(node) + '\n'
        return vms[:-1]


    __repr__ = __str__


    def belongsToGroup(self, vmName):

        found = None

        for vm in self.vmsList:
            if vm.getVmName() == vmName:
                found = vm

        return found


    def addNode(self, vmName, vmsContainer):
        
        vmNode = self.belongsToGroup(vmName)
        if (vmNode is None):
            print("Adding VM: %s" % vmName)
            self.vmsList.append(VirtualMachine(vmsContainer, vmName))
        else:
            print("%s is already part of the group" % vmName)


    def removeNode(self, vmName):

        vmNode = self.belongsToGroup(vmName)
        if ( vmNode is None):
            print("%s is not part of the group" % vmName)
        else:
            self.vmsList.remove(vmNode)

    def printCurrent(self):

        for vm in self.vmsList:
            print("%s - Current Snapshot: %s" % (vm, vm.getCurrentSnapshot()))


    def isGroupDown(self, timeOut):
        #If all the VMs in the managed scope are down

        groupDown = False
        timer=20
        while (not groupDown) and (timeOut>=0):
            groupDown = True
            timeOut -= timer
            for node in self.vmsList:
                if not node.isVmDown():
                    groupDown = False
                    print("%s is UP" % node)
                elif node.isVmDown():
                    groupDown = groupDown and True
                if not groupDown:
                    sleep(timer)
        return groupDown


    def printGroupState(self):

        for node in self.vmsList:
            if not node.isVmDown():
                print("%s is UP" % node)
            elif node.isVmDown():
                print("%s is DOWN" % node)


    def printVmsList(self):

        for node in self.vmsList:
            print("%s" % node.getVmName())


    def getVmsList(self):

        return self.vmsList


    def saveGroup(self, filename):

        with open(filename,'w') as outputfile:
                for node in self.vmsList:
                    outputfile.write("%s\n" % node.getVmName())


    def printSnapshotsTree(self):

        for node in self.vmsList:
            print(chr(9556) + chr(9552) * ( 2 + len(node.getVmName())) + chr(9559))
            print("%s %s %s" % (chr(9553), node.getVmName(), chr(9553)))
            print(chr(9562) + chr(9552) * ( 2 + len(node.getVmName())) + chr(9565))
            node.printSnapshotsList()


    def shutdownGroupGuestOS(self):

        for node in self.vmsList:
            if not node.isVmDown():
                print("Shutting down VM: %s" % node.getVmName())
                node.shutdownGuestOs()
            else:
                print("VM: %s already Powered Off" % node.getVmName())


    def powerOnGroup(self):

        for node in self.vmsList:
            if node.isVmDown():
                print("Powering UP VM %s" % node.getVmName())
                node.powerOn()
            else:
                print("VM %s is already UP" % node.getVmName())


    def takeSnapshot(self, snapshotName, snapshotDescription):

        ts = time.time()
        timeStamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        for node in self.vmsList:
            node.takeSnapshot(snapshotName, snapshotDescription, timeStamp)


    def revertToCurrentSnapshot(self):

        for node in self.vmsList:
            node.revertToCurrentSnapshot()


    def goToSnapshot(self, snapshot):

        for node in self.vmsList:
            node.goToSnapshot(snapshot)


    def removeSnapshot(self, snapshot, consolidate):

        for node in self.vmsList:
            node.removeSnapshot(snapshot, consolidate)


class VirtualMachine:
    """ 
        Attributes:
        Name of the Virtual Machine
        List of Snapshots        
    """

    def __init__(self, vmsContainer, vmName):

        vm = False
        for vmobject in vmsContainer.view:   
            if vmobject.name == vmName:
                vm = vmobject    
                break

        if not vm:
            raise Exception("Virtual Machine %s doesn't exists" % vmName)

        self.vm = vm

        self.snapshotsList = []

        if self.vm.snapshot:
            self.snapshotsList = self.loadSnapshotsList(self.vm.snapshot.rootSnapshotList, 0, 0)
          
    
    def reloadSnapshotsList(self):

        if self.vm.snapshot:
            self.snapshotsList = self.loadSnapshotsList(self.vm.snapshot.rootSnapshotList, 0, 0)       


    def loadSnapshotsList(self, snapshotsObjectsFromVSphere, snapShotParent, snapshotLevel):

        snapshotsList = []

        if self.vm.snapshot:
            for snapshotFromVSphere in snapshotsObjectsFromVSphere:
                snapshotNode = Snapshot(snapshotFromVSphere, snapShotParent, snapshotLevel)
                if snapshotFromVSphere.snapshot == self.vm.snapshot.currentSnapshot:
                    snapshotNode.makeSnapshotCurrent()
                snapshotsList.append(snapshotNode)
                snapshotsList = snapshotsList + self.loadSnapshotsList(snapshotFromVSphere.childSnapshotList, snapshotFromVSphere.id, snapshotLevel + 1)
        
        return snapshotsList
    

    def getCurrentSnapshot(self):

        self.reloadSnapshotsList()

        for snapshot in self.snapshotsList:
            if snapshot.isCurrent:
                return snapshot.getSnapshotName()


    def printSnapshotsList(self):

        self.reloadSnapshotsList()

        for snapshot in self.snapshotsList:
            level = chr(9492) +  chr(9472) * 2
            if snapshot.getSnapshotLevel() == 0:
                level = " " * 2 + level

            if snapshot.getSnapshotLevel() > 0:
                level = " " * snapshot.getSnapshotLevel() * 5 + "  " +  level

            print("%s [%s] %s " % (level, snapshot.getSnapshotId(), snapshot))

            if snapshot.isCurrent:
                level = " " * 5 + level
                print("%s %s" % (level, "You are Here"))


    def getHost(self):

        return self.vm.runtime.host.name


    def __str__(self):

        return "VM Name: " + self.vm.name


    __repr__ = __str__


    def getVmName(self):

        return self.vm.name


    def isVmDown(self):

        if self.vm.runtime.powerState == 'poweredOff':
            return True
        else:
            return False


    def shutdownGuestOs(self):

        if not self.isVmDown():
            self.vm.ShutdownGuest()


    def powerOn(self):

        self.vm.PowerOn()


    def takeSnapshot(self, snapshotName, snapshotDescription, timeStamp):

        dumpMemory = False
        quiesce = False
        snapshotDescription += (' on ' + timeStamp)
        print("Taking snapshot: %s for %s" % (snapshotName, self.getVmName()))
        WaitForTask(self.vm.CreateSnapshot(snapshotName, snapshotDescription, dumpMemory, quiesce))


    def revertToCurrentSnapshot(self):

        print("Reverting vm: %s to current snapshot" % self.vm.name)
        WaitForTask(self.vm.snapshot.currentSnapshot.RevertToSnapshot_Task())


    def goToSnapshot(self, snapshotname):

        self.reloadSnapshotsList()
        found = False
        for node in self.snapshotsList:
            if snapshotname == node.getSnapshotName():
                print("Reverting vm: %s to snapshot [%s] %s" % (self.vm.name, node.getSnapshotId(), snapshotname))
                WaitForTask(node.getSnapshotObj().RevertToSnapshot_Task())
                found = True
                break
        if not found:
            print("Snapshot %s not found in VM: %s" % (snapshotname, self.vm.name))
            if not self.isVmDown():
                print("Shutting down VM: %s" % self.vm.name)
                self.shutdownGuestOs()


    def removeSnapshot(self, snapshotname, consolidate):

        self.reloadSnapshotsList()
        for node in self.snapshotsList:
            if snapshotname == node.getSnapshotName():
                print("Deleting snapshot [%s] %s of VM %s" % (node.getSnapshotId(), snapshotname, self.vm.name))
                WaitForTask(node.getSnapshotObj().RemoveSnapshot_Task(consolidate))
                break    

class Snapshot:

    def __init__(self, snapshot, snapshotParent, snapshotLevel):

        self.snapshot = snapshot

        self.snapshotParent = snapshotParent

        self.isCurrent = False

        self.level = snapshotLevel

 
    def getSnapshotObj(self):
 
        return self.snapshot.snapshot


    def getSnapshotId(self):

        return self.snapshot.id


    def getSnapshotLevel(self):

        return self.level
    

    def getSnapshotName(self):

        return self.snapshot.name


    def getSnapshotParent(self):    

        return self.snapshotParent


    def makeSnapshotCurrent(self):

        self.isCurrent = True


    def __str__(self):
        return self.snapshot.name

    __repr__ = __str__


def loadList(nodes):
    """Loads list from a file or a comma separated string"""

    groupFile = Path(nodes)
    if groupFile.is_file():
        with open(nodes) as nodesFile:
            nodesList = nodesFile.read().splitlines()
    else:
        nodesList = nodes.split(',')
    return nodesList
    

class CmdLine(Cmd):
    def __init__(self):

        Cmd.__init__(self)
        self.prompt = "RUN "
        self.intro = "READY."
        self.vSphereConnection = None


    def do_connect(self, args):
        """Connect to vSphere: 
            Usage: connect [user:password@vCenterServer]
        """

        logInInfo = getLogInInfo(args)
        print("Trying to connect to VCENTER SERVER . . .")
        self.vSphereConnection = Vsphere(logInInfo[0],logInInfo[1], logInInfo[2])
        print("Connected to VCENTER SERVER !")


    def do_printallvms(self, args):
        """Prints all the VMs in the Virtual Machine container view
            Usage: printallvms [grep substring]
            Example: printallvms grep myvm --> prints all VMs that contain 'myvm' in the name"""

        if not self.vSphereConnection:
            print("Please connect to vSphere")
            return -1
        if len(args) == 0:
            for vm in self.vSphereConnection.getContainer().view:
                print(vm.name)        
        else:
            parsedArgs = args.split(' ')
            if len(parsedArgs) > 0 and len(parsedArgs) <= 2:
                if parsedArgs[0] != "grep":
                    print("Command not recognized")
                elif len(parsedArgs) == 1:
                    print("Missing argument: grep substring")
                else:
                    for vm in self.vSphereConnection.getContainer().view:
                        if parsedArgs[1] in vm.name:
                            print(vm.name)
            else:
                print("Too many arguments")        
                

    def do_printgroup(self, args):
        'Prints VMs defined by the applied group'

        self.group.printVmsList()


    def do_loadgroup(self, nodes):
        'Applies group based on a list of VMs in a file or a comma separated list:   loadgroup </path/to/file> or loadgroup testVM1,testVM2,testVM3'

        self.group = Group(loadList(nodes), self.vSphereConnection.getContainer())
    

    def do_addvm(self, node):
        """Adds a VM to the current group
            Usage:  addtogroup testVM1"""
        
        if not node:
            print("Missing VM Name")
        else:
            self.group.addNode(node, self.vSphereConnection.getContainer())


    def do_removevm(self, node):
        """Removes a VM from the current group
            Usage: removefromgroup testVM1"""
        
        self.group.removeNode(node)


    def do_savegroup(self, filename):
        'Dumps the current group to a file: savegroup </path/to/file>'

        if not filename:
            print("Please provide file name")
        else:
            self.group.saveGroup(filename)


    def do_printsnapshots(self, args):
        'Prints all snapshots'

        self.group.printSnapshotsTree()


    def do_printcurrentsnapshot(self, args):
        'Prints current snapshot'

        self.group.printCurrent()


    def do_revertcurrent(self, args):
        """Reverts to current snapshot.  A modifier can be used to restart the VMs after reverting.
            Usage: revertcurrent restart"""

        self.group.revertToCurrentSnapshot()
        if args == 'restart':
            self.group.powerOnGroup()
                    

    def do_gotosnapshot(self, args):
        """ Goes to a snapshot.  A modifier can be used to restart the VMs after reverting.
            Usage: gotosnapshot <snapshotname> restart"""

        if len(args) == 0:
            print("Missing Snapshot name")
        else:
            parsedArgs = args.split(' ')
            if len(parsedArgs) > 2:
                print("Too many arguments")
            elif len(parsedArgs) >= 1:
                self.group.goToSnapshot(parsedArgs[0])
            if len(parsedArgs) == 2:
                if parsedArgs[1] == 'restart':
                    self.group.powerOnGroup()


    def do_removesnapshot(self, args):
        """Removes snapshot. A modifier can be used to restart the VMs after reverting. 

        Usage : gotosnapshot <snapshotname> restart"""

        if len(args) == 0:
            print("Missing Snapshot name")
        else:
            parsedArgs = args.split(' ')
            if len(parsedArgs) > 2:
                print("Too many arguments")
            elif len(parsedArgs) == 1:
                self.group.removeSnapshot(parsedArgs[0], False)
            elif len(parsedArgs) == 2:
                if parsedArgs[1] == 'withchildren':
                    self.group.removeSnapshot(parsedArgs[0], True)
                else:
                    print("Wrong argument.  Use withchildren if you want to remove all children snapshots")


    def do_getstate(self, args):
        'Gets power state of the VMs in the group'

        self.group.printGroupState()


    def do_poweron(self, args):
        'Powers on the VMs in the group'

        self.group.powerOnGroup()


    def do_shutdown(self, args):
        'Shuts down the VMs in the group'

        self.group.shutdownGroupGuestOS()
                

    def do_takesnapshot(self, args):
        """ Take snapshot.  Description is optional (A time stamp will be added).
            The VMs will be shutdown to take a clean snapshot.  This behaviour is by default.
            Usage: takesnapshot <snapshotname> 'This is a description'"""

        parsedArgs = args.split(" ")
        description = ""

        if len(parsedArgs) == 1:
            description = "Taken by pyvmgr"
            
        elif len(args) >= 2:
            description = " ".join(parsedArgs[1:])
            
        self.group.shutdownGroupGuestOS()
        if self.group.isGroupDown(timeOut):
            self.group.takeSnapshot(parsedArgs[0], description)
        else:
            print("Could not power down group, snapshot not taken")


def connectToVSphere(args):

            logInInfo = getLogInInfo(args)
            return Vsphere(logInInfo[0],logInInfo[1], logInInfo[2])


def getLogInInfo(args):

    if args == '':
        vCenterServer = input("Enter vCenter Server name or IP address:")
        vCenterUserName = input("Enter vCenter Username:")
        vCenterPassword = getpass.getpass(prompt='Enter the password for user %s at vCenter server %s: ' % (vCenterUserName,vCenterServer))

    elif len(args.split(" ")) == 1:
        connectionArgs = args.split('@')
        if len(connectionArgs) == 1:
            vCenterServer = connectionArgs[0]
            vCenterUserName = input("Enter vCenter Username:")
            vCenterPassword = getpass.getpass(prompt='Enter the password for user %s at vCenter server %s: ' % (vCenterUserName,vCenterServer))
            
        elif len(connectionArgs) == 2:
            vCenterServer = connectionArgs[1]
            vCenterCredentials = connectionArgs[0].split(':')
            vCenterUserName = vCenterCredentials[0]
            if len(vCenterCredentials) == 1:    
                vCenterPassword = getpass.getpass(prompt='Enter the password for user %s at vCenter server %s: ' % (vCenterUserName,vCenterServer))
            elif len(vCenterCredentials) == 2:
                vCenterPassword = vCenterCredentials[1]

    else:
        print("Error, too many arguments")

    return  (vCenterServer, vCenterUserName, vCenterPassword)

def main():
    # Global Configuration settings
    global timeOut
    timeOut = 180 
    
    #Shell
    console = CmdLine()
    console.cmdloop()

# Start program
if __name__ == "__main__":

    main()
    print()