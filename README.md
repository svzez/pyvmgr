# pyvmgr.py
A python script to manage groups of VMs from vSphere.  
It's a wrapper for using pyvmomi

The idea behind it is to be able to take/revert to/delete/list snapshots, poweron and off groups of VMs.  This is useful when used in a test environment, not intended for production.

## Pre requisites
* Python 3.4+
* cmd2
* pyvmomi

## Usage
```sh
./pyvmgr.py
READY.
RUN help

Documented commands (type help <topic>):
========================================
_relative_load  help                  py                savegroup
addvm           history               pyscript          set
loadgroup       load                  quit              shell
cmdenvironment  poweron               removevm          shortcuts
connect         printallvms           removesnapshot    show
edit            printcurrentsnapshot  revertcurrent     shutdown
getstate        printgroup            run               takesnapshot
gotosnapshot    printsnapshots        save

RUN

```

## Examples
The same commands used in an interactive session can be passed as parameters:
```./pyvmgr.py "connect user:passwor@vcenter.priv" "loadgroup test" printgroup printsnapshots
READY.
Trying to connect to VCENTER SERVER . . .
Connected to VCENTER SERVER !
testVM1
testVM2
╔═════════╗
║ TestVM1 ║
╚═════════╝
  └── [23] Snapshot1
       └── [24] test
            └── [25] test3
                 └── [26] Snapshot2
                      └── [33] AnotherTest2
  └── [34] Clean
       └── [35] Test123
            └── [36] More
       └── [41] test5
            └── You are Here
╔═════════╗
║ TestVM2 ║
╚═════════╝
  └── [1] Clean
       └── [2] More
            └── [3] Test
                 └── [4] Snapshot1
                      └── [5] Test123
                           └── You are Here
       └── [15] Clean2
            └── [16] test3
                 └── [21] test5
RUN

```

Shutdowns GuestOS of the VMs in the group, then quits
```sh
./pyvmgr.py "connect user:password@vcenter.priv" "loadgroup test" shutdown quit
READY.
Trying to connect to VCENTER SERVER . . .
Connected to VCENTER SERVER !
Shutting down VM: TestVM1
Shutting down VM: TestVM2
```

A few commands in the interactive view:

```sh
./pyvmgr.py
READY.
RUN connect
Enter vCenter Server name or IP address:vcenter.priv
Enter vCenter Username:username
Enter the password for user username at vCenter server vcenter.priv:
Trying to connect to VCENTER SERVER . . .
Connected to VCENTER SERVER !
RUN loadgroup test
RUN getstate
VM Name: TestVM1
VM Name: TestVM2
RUN poweron
Powering UP VM TestVM1
Powering UP VM TestVM2
RUN

```