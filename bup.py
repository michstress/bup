#!/usr/bin/python

config_found=True

try:
    import bup_config
    print("bup_config found!")
except ImportError:
    pass
    try:
        import bup_config_default as bup_config
        print("bup_config_default found!")
    except ImportError:
        pass
        print("!NO bup_config or bup_config_default found!")
        config_found=False

import os, sys, getopt, subprocess, time, shutil, datetime, errno, tarfile

now = datetime.datetime.now()

#automate: http://www.panticz.de/node/629

def phelpexit(ecode):
    print """
    This script is intended to be called in regular time intervals (automated) in order to organize automated backups

    By utilizing this script your data should be safe against:
    - HDD failure: A backup on external HDD + data on usb device will recover your complete data.
    - Pyhsical harm to your apartment(fire/burglary) or Malicious blackmail encryption: The initial backup is stored on backup device, the differential is encrypted in the cloud.
    - Data capturing (The data send to the cloud is encrypted)
    Recovery:
    - Minimalisitc time machine: Depending on the size you allow you incremental backup to grow, you can instantly look at past version by Browsing the incremental backup dir
    - On HDD Crash you will need to retrieve the HDD with initial backup, copy it to new HDD, plus use the USB Stick to apply all changes
    - On apartment lost, you will need to retrieve the HDD with initial backup, copy it to new HDD, retrieve incremetnal backups from cloud, decrypt it and apply to new HDD copy

    My setup:
    _______________________________
    | NAS                          |
    | +- MyData 1TB                |   (optional)
    | +- CloudSync 100GB           |  _____|_______
    | +- IncBackups 500GB          |__| USB-Stick |   
    | +- targz (local or on usb) => __  100GB     |
    |______________________________|  |___________|      __     __   ____
    _________________                                  _/  \___/  \_/    \
    | Backup HDD at |                                 /   Cloud Drive____/
    | friends place |                                 \___ 100GB ____/
    | (1TB)         |                                    \______/
    |_______________|

    This is the most low cost setup I could think of which still ensures no data get's lost.
    You can have a more easy backup solution if you invest in more cloud space and or a friends place,
    and buy a NAS, which does rsync regularily, capturing data from your place.
    Anyhow, back to this solution:

    1. There is a harddrive, which holds the data to be back upped (NAS/MyData)
    2. There is an incremental backup folder available which can be utilized for storing the backup data (NAS/IncBackups)
        - The space in the incremental backup folder will need to hold all backup data (which can be reduced by defining an exclude list)
          ( I typically exclude non personal movie files directories, download folders, temp folders, the backup folder! )
        - the space on the incremental backup folder needs to be large enough to hold space for differential backups
    3. (optional) There is a usb-like-folder which holds the compressed differntial backup data.
       Main reason is, that if the cloud is down, you still have a place where your data is located :)
    4. There is a syncFolder available (this one is within my 1.5TB available for backup). The folder holds the encrpyted data
       of differential backups. I have about 100GB google drive cloud space, which is used to auto sync data (by other means
       than this script).
    5. One more harddrive to hold the initial (none differential) backup (In my case a 1TB usb device), which is then 
       transitioned to a friends home.


    How to get started (after having copied bup.py to a path located within your $PATH):
    
    1. Create Initial differential backup 
        
         bup.py -s /MyDataFolder -i /IncBackupFolder

       You will find that your IncBackupFolder now contains a snapshot via hardlinks of your complete MyDataFolder.
       Something like:  /IncBackupFolder/snap2015-12-23__180320HlCp 
                        /IncBackupFolder/snapLastHlCp

    2. rsync this data to your Backup HDD
       
       rsync -a --delete --progress /IncBackupFolder/snapLastHlCp/ /media/myHddMount   
       TODO: Test incremental backup on shifting src?
       TODO: How to find date on recovery? 
  
    3. execute daily (via crontab or similiar) and ensure cloudsyncfolder is setup to pushed to the cloud regularily:
          
          bup.py -s /MyDataFolder -i /IncBackupFolder -t /UsbStickFolder -c /CloudSyncFolder -k SomeLengthyKeyInPlainTextThatYouNeverForget

    4. monitor you /CloudSyncFolder, if it is filled 80%, retrieve BackUp HDD and sync it again, after that delete your CloudSyncFolder.

       rsnyc -a --delete --progress /IncBackupFolder/snapLastHlCp/ /media/myHddMount 

       delete stuff in IncBackupFolder, CloudSyncFolder, UsbStickFolder. I keep some stuff, so I can still go back some days.


    Further configuration:
       place a bup_config.py file in the same directory as you copied the bup.py file.
       Example contents:

#!/usr/bin/python

# bup tries to compress contents, before it is pushed to the cloud. Here you can define file endings which
# are not compressed, because compressing thems just consumes power, but does not compress the file
def getDoNotCompress():
    return [".mp3",".7z",".zip",".gz","jpeg","jpg","gif","dng","png","avi","mpeg","mov","wmv","mp4"]

# directories within your MyDataFolder directory which shouldn't be backuped.
def getExcludeDirs():
    return [ 
        "/2wd",
        "/video", 
        "/public",
        "/@*",
        "/computer" ]
    """
    sys.exit(ecode)

def symlink_force(target, link_name):
    try:
        os.symlink(target, link_name)
    except OSError, e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
        else:
            raise

def execute_shell(cmd, printLastArg=True):
    if printLastArg:
        print(" ".join(cmd))
    else:
        print(" ".join(cmd[:-1]))
    shproc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    if shproc != None:
        shproc.stdin.close()
        shproc.wait() # wait shell process to exit
        if shproc.returncode != 0:
            sys.exit("Error: " + cmd[0] + " failed during execution")
    else:
        sys.exit("Error: Could not execute " + cmd[0])


def main(argv):
    srcPath = ''
    destPath = ''
    targzPath = ''
    cryptPath = ''
    cryptKey = ''
    
    try:
        opts, args = getopt.getopt(argv,"hs:i:d:t:c:k:",["src=","dest=","targz=","crypt=","key="])
    except getopt.GetoptError:
        print 'bup.py -s <srcPath> -d <destPath> -t <targzPath> -c <cryptPath> -k <key>'
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
        	print 'bup.py -s <srcPath> -i <incbackup> -t <targzPath> -c <cryptPath> -k <key>'
      		sys.exit()
      	elif opt in ("-s", "--src"):
        	srcPath = arg
      	elif opt in ("-d", "--dest"): #old incbackup, left for compatibility 
        	destPath = arg
      	elif opt in ("-i", "--incbackup"):
        	destPath = arg
      	elif opt in ("-t", "--targz"):
        	targzPath = arg
      	elif opt in ("-c", "--crypt"):
        	cryptPath = arg
      	elif opt in ("-k", "--key"):
        	cryptKey = arg

    
    if srcPath == '' or destPath == '':
        sys.exit(2)

    snapshotdate = now.strftime("%Y-%m-%d__%H%M%S")
    
    print ("\n ____     __  __  ____  ")  
    print ("/\\  _`\\  /\\ \\/\\ \\/\\  _`\\")  
    print ("\\ \\ \\L\\ \\\\ \\ \\ \\ \\ \\ \\L\\ \\")
    print (" \\ \\  _ <'\\ \\ \\ \\ \\ \\ ,__/")
    print ("  \\ \\ \\L\\ \\\\ \\ \\_\\ \\ \\ \\/")
    print ("   \\ \\____/ \\ \\_____\\ \\_\\")
    print ("    \\/___/   \\/_____/\\/_/ ...............V0.1 (2015-09)")
    print ("                                         Start: "+ snapshotdate +"\n")

    if config_found:
        doNotCompress = tuple(bup_config.getDoNotCompress())
        excludeArgs = []
        for aDir in bup_config.getExcludeDirs():
            excludeArgs.append('--exclude')
            excludeArgs.append(aDir)
    else:
        doNotCompress = tuple([".real_nothing"])
        excludeArgs = ['--exclude', 'real_nothing']

    snapshothlcp = os.path.join(destPath, "snap" + snapshotdate + "HlCp")
    os.makedirs(snapshothlcp)

    snapshothlcpln =  os.path.join(destPath, "snapLastHlCp")

    initial_backup = False
    if not os.path.exists(snapshothlcpln):
        initial_backup = True

    if initial_backup:
        execute_shell(["rsync"] + ["-a", "--delete"] + excludeArgs + [srcPath+"/", snapshothlcp])
    else:  
        execute_shell(["rsync"] + ["-a", "--delete", "--link-dest", snapshothlcpln ] + excludeArgs + [srcPath+"/", snapshothlcp])

    symlink_force(snapshothlcp, snapshothlcpln)
    
    if targzPath != '' and not initial_backup:
        savedPath = os.getcwd()        
        os.chdir(snapshothlcp)
        snapshotdiffcptargz = os.path.join(targzPath, "snap" + snapshotdate + "DiffCpComp.tar.gz")
        snapshotdiffcptar = os.path.join(targzPath, "snap" + snapshotdate + "DiffCpUncomp.tar")
        tocpComp = []
        tocpUncomp = []
        for root, dirs, files in os.walk(snapshothlcp): # Walk directory tree
            for f in files:
                try:
                    if os.stat(os.path.join(root, f)).st_nlink == 1:
                        if f.lower().endswith(doNotCompress):
                            tocpUncomp.append(os.path.join(root[len(snapshothlcp)+1:], f))
                        else:
                            tocpComp.append(os.path.join(root[len(snapshothlcp)+1:], f))
                except IOError:
                    print "Error: stat invalid for " + os.path.join(root,f)

        with tarfile.open(snapshotdiffcptargz, "w:gz") as targz:
            for filepath in tocpComp:
                print("...adding: " + filepath)
                targz.add(filepath)
        with tarfile.open(snapshotdiffcptar, "w") as targz:
            for filepath in tocpUncomp:
                print("...adding: " + filepath)
                targz.add(filepath)
        os.chdir(savedPath)                
        symlink_force(snapshotdiffcptargz,os.path.join(destPath, "snapLastDiffCpComp.tar.gz"))
        symlink_force(snapshotdiffcptar,os.path.join(destPath, "snapLastDiffCpUncomp.tar"))

        if cryptPath != '' and cryptKey != '':
            snapshotdiffcptargzenc = os.path.join(cryptPath, "snap" + snapshotdate + "DiffCpComp.tar.gz.enc")
            snapshotdiffcptarenc = os.path.join(cryptPath, "snap" + snapshotdate + "DiffCpUncomp.tar.enc")

            execute_shell(["openssl","enc","-aes-256-cbc","-salt","-in",snapshotdiffcptargz,"-out",snapshotdiffcptargzenc,"-k", cryptKey], False)
            execute_shell(["openssl","enc","-aes-256-cbc","-salt","-in",snapshotdiffcptar,  "-out",snapshotdiffcptarenc  ,"-k", cryptKey], False)
            symlink_force(snapshotdiffcptargzenc,os.path.join(destPath, "snapLastDiffCpComp.tar.gz.enc"))
            symlink_force(snapshotdiffcptarenc,os.path.join(destPath, "snapLastDiffCpUncomp.tar.enc"))

    else:
        if initial_backup:
           print("This is the first run for the destination directory " + destPath)
#           print("Hence no diff file to the last backup of the destination directory could be established!")
#           print("On further runs with the same destination directory (if the -targz option is used)")
#           print("A diff <targz>/'date'DiffCpComp.tar.gz (and optional a DiffCpUncomp.tar.gz) will be created")
#           print("Holding all files that changed since last run of bup.py!")
#           print("You should NOW backup the destination directory " + rsyncDir)
#           print("to a large enough backup medium of your choice!")
#           print("ike so:")
# first run for the destination directory " + rsynDir)
#        rsync -a --delete --progress /volume1/2wd/c42y/ $1/usbshare/c42y > /volume1/2wd/logs/rsyncC42Y2Seagate`date -u +%Y-%m-%d__%H%M%S`.log

    print("Done ("+ snapshotdate +")")
    
    
if __name__ == "__main__":
	main(sys.argv[1:])

