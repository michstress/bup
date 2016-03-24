#!/usr/bin/python

import sys, getopt, os, re, binascii, operator, datetime, shutil
from sets import Set
from shutil import move

def usage(ecode):
    u = """
   Folderwatch!

   With folderwatch you can monitor/record changes on a sepcifically changed folder.
   Changes are not monitored by the filesystem, but by using folderwatch regularily,
   for example by a scheduled chron job.
   Advantages are independence of filesystem, disadvantage is that conclusions are
   drawn by observation, hence it is less acurate (Some events might get missed).
   You can utilize it to draw an history of your home directory, or any directory
   you want to monitor activity on. You can lookup, when files were edited, moved,
   copied, deleted + you can activate guards which monitor directories for unwanted changes
   The standard activated guard is that deletes trigger a violation as well as edits
   without an active copy/backup. Some Examples:

    - My mp3 collection usually does not shrink, only get's extended. Hence as long
      as I only extend it everything is fine, but when a file is modified or deleted
      folderwatch reports a violation, and you can review if the delete was intended
      or done my mistake (or other reasons)
    - Sames is true for my pictures folder
    - I have some finished projects, building a house, studying material, etc...
      which I do not expect to change, but stil think it important to keep.
      I protect it with a #### rule, so that I do not accidently store files there
      or manipulate or delete. If I do I will get a vialoation, and I can research 
      what went wrong

   You can also do an query on the data and find out when a file as evolved:
      tbd.

   Like said, folderwatch needs to be triggered manually, or by a cron job. Upon
   each start the folling parameters can be provided:
    -f/folderwatchhomepath This is the path were the data about the scans is kept.
                           defaults to ~/.fw
    -m/monitorpath         Path that should be monitored for changes, defaults to ~
                           (In a cron job I monitor all user directories... /home)
    -c/configfile          Instead of passing the paramters via commandline, a 
                           file containing the parameters can be specified
    -i/ignore              Within the given path to monitor, ignore all file
                           which match the pattern given within ignore
    -g/guard               establish a guard for a given directory
                           jdoe/work/#**#       allows all file operation 
                           jdoe/house/####      allows no file operations 
                           jdoe/mp3/##+#        files may only be added
                           jdoe/pictures/##>#   adds and moves allowed (reorginization possible)
                           jdoe/coding/#e+#     Edits and adds allowed
                           jdoe/prototype/#e>#  Edits, adds and moves allowed
                           jdoe/whatever/#E+#   Edits with backup allowed and adds allowed
                           jdoe/default/#E>#    non matching path, nothing to guards...

"""
    sys.exit(ecode)

now = datetime.datetime.now()

crc_f_pos = 0
size_pos = 1
op_pos = 2
run_pos = 3
fs_pos = 4
cut_off = 20

fileRepo = dict()    

class fpathes:
    def __init__(self, pathes = None, defacc = False):
        self.accs = []
        self.ps = []
        if pathes != None:
            for path in pathes:
                self.ps.append(path.rstrip())
                self.accs.append(defacc) 

    def add(self, path, acc = False):
        try:
            i = self.ps.index(path.rstrip())
            self.accs[i] = acc
        except ValueError:
            self.ps.append(path.rstrip())
            self.accs.append(acc)

    def index(self, path):
        for i, p in enumerate(self.ps):
            if p == path:
                i = self.ps.index(path)
                #print("(" + str(i) + "/#" + path + "#) Index on: " + pPs(self.ps))
                return i
        #print("(-1/#" + path + "#) Index on: " + pPs(self.ps))
        return -1
            
    def rm(self, path):
        try:
            i = self.ps.index(path.rstrip())
            self.ps.pop(i)
            self.accs.pop(i)
        except ValueError:
            pass

    def filter(self, acc):
        r = []
        for i, p in enumerate(self.ps):
            if self.accs[i] == acc: 
                r.append(p)
        return r 

    def account(self, i, acc = True):
        self.accs[i] = acc

class fentry:
    def __init__(self, size, op, run, pathes = None, acc = True):
        self.size = size
        self.op = op
        self.run = run
        self.pathes = fpathes(pathes, acc)

    def accountedFileExists(self, acc = True):
        return len(self.pathes.filter(acc)) > 0

    def toline(self, k):
        line = '%s;%d;%s;%s;' % (k, self.size, self.op, self.run)
        if self.op == 'd' or self.op == 'e':
            line += ';'.join(self.pathes.ps)
        else:
            line += ';'.join(self.pathes.filter(True))
        return line + '\n'

class newkey:
    def __init__(self, key, path, size, op):
        self.key = key
        self.path = path
        self.size = size
        self.op = op


def getcrc(f, numOfChunks=2, CHUNK=2**16):
    result = 0
    chunkCtr = 0
    fsize = os.path.getsize(f)
    ftime = os.path.getmtime(f)
#   Rely on size and time for speed....
#    with open(f, "rb") as crcF:
#        while chunkCtr < numOfChunks:
#            chunk = crcF.read(CHUNK)
#            if not chunk:
#                break
#            result = binascii.crc32(chunk, result)
#            chunkCtr += 1
   
    return '{:0>10}'.format(str(result & 0xFFFFFFFF)) + '_' + \
           '{:0>8.0f}'.format(ftime) + '_' + \
           '{:0>8}'.format(str(fsize)), fsize 

def readDb(dbPath):
    global filerRepo,verbose
    if os.path.exists(dbPath):
        if verbose:
            print("Reading database: "+ dbPath)
        with open(dbPath,'r') as dbFile:
            for line in dbFile:
                entry = line.split(';') #[crc_filename;path;state;date]
                if len(entry) <= fs_pos:
                    continue
                else:
                    f = fentry(int(entry[size_pos]), entry[op_pos], entry[run_pos], entry[fs_pos:], False)
                    fileRepo[entry[crc_f_pos]] = f

def queryDb(fwBPath, ops, path2filter):
    global fileRepo,verbose
    if len(ops) != 1 or ops not in 'dernm*': #(d)elete (e)volve (r)eadded (n)ew (m)oved
        print "Error: Invalid operation: " + ops
        usage(2)
    p2f = os.path.abspath(path2filter).replace('/','_')   
    for fn in os.listdir(fwBPath):
        if os.path.isdir(os.path.join(fwBPath, fn)):
            if len(fn) >= len(p2f) and fn.startswith(p2f):
                readDb(os.path.join(fwBPath, fn, "fw.db"))
                for k, f in fileRepo.iteritems():
                    if ops == '*' or f.op == ops:
                        for p in f.pathes.ps:
                            print p
            elif len(p2f) > len(fn) and p2f.startswith(fn):
                subdir = os.path.abspath(path2filter)[len(fn)+1:]
                if verbose:
                    print "Searching for " + subdir + " in " + fn
                readDb(os.path.join(fwBPath, fn, "fw.db"))
                for k, f in fileRepo.iteritems():
                    if ops == '*' or f.op == ops:
                        for p in f.pathes.ps:
                            if p.startswith(subdir):
                                print p
                 
    sys.exit(0)


#def fequals(o_f, o_crc, o_size, n_f, n_crc, n_size):
#    return (o_crc == n_crc and o_size == n_size)

#def getkey(fid, fn):
#    return crc, size, fn)

def pPs(pathes, cut=cut_off):
    ps = []
    for p in pathes:
        if len(p) > cut:
            ps.append('..' + p[len(p)-cut-2:])
        else:
            ps.append(p)
    return "#" + "#, #".join(ps) + "#"
    
def main(argv):
    
    global filerRepo, verbose 
    monitorPath       = ''
    fwBPath           = '' 
    verbose           = False
    vverbose          = False
    news              = []
    newpathes         = dict()
    badpathes         = dict()
    ops               = '*'
    guards            = []
    configFn          = None
    ignores           = []
    path2filter       = ''
    query             = False
    others            = []

    def guardcheck(evs, dels, added, bEvs, mDels):
        vs = []
        for f in evs + dels + added:
            fsnips = f.split('/')
            broken = False
            matched = False
            for gsnips in guards:
                i = 0
                while not broken and not matched and i < len(fsnips) and i < len (gsnips):
                    if fsnips[i] != gsnips[i]:
                        if gsnips[i] == '#**#':  #Any modification allowed
                            matched = True
                            break
                        elif gsnips[i] == '####':   #No changes allowed
                            matched = True
                            broken = True
                            vs.append((f, 'frozen violation!', '/'.join(gsnips)))
                        elif gsnips[i] == '##+#':  #adds allowed
                            matched = True
                            if not f in added:
                                vs.append((f, 'edit or delete violation!', '/'.join(gsnips)))
                                broken = True
                        elif gsnips[i] == '##>#':  #adds and moves allowed
                            matched = True
                            if f in dels and not mDels:
                                vs.append((f, 'delete violation!', '/'.join(gsnips)))
                                broken = True
                            if f in evs:
                                vs.append((f, 'edit violation!', '/'.join(gsnips)))
                                broken = True
                        elif gsnips[i] == '#e+#':  #Edits and adds allowed
                            matched = True
                            if f in dels:
                                vs.append((f, 'delete violation!', '/'.join(gsnips)))
                                broken = True
                        elif gsnips[i] == '#e>#':  #Edits, adds and moves allowed
                            matched = True
                            if f in dels and not mDels:
                                vs.append((f, 'delete violation!', '/'.join(gsnips)))
                                broken = True
                        elif gsnips[i] == '#E+#':  #Edits with backup allowed and adds allowed
                            matched = True
                            if f in dels:
                                vs.append((f, 'delete violation!', '/'.join(gsnips)))
                                broken = True
                            elif f in evs and not bEvs:
                                vs.append((f, 'edit without backup violation!', '/'.join(gsnips)))
                                broken = True
                        elif gsnips[i] != '#E>#': #non matching path, nothing to guards...
                            break
                    i += 1
            if not broken and not matched: # if nothing is defined assume standard protection: '#E>#'
                if f in dels and not mDels:
                    vs.append((f, 'delete violation!', '--default--'))
                elif f in evs and not bEvs:
                    vs.append((f, 'edit without backup violation!', '--default--'))
        return vs


    if argv[0] == 'q' or argv[0] == '--query':
        query = True;
        try:
            opts, args = getopt.getopt(argv[1:],"hf:o:p:v",["folderwatchhomepath=", "operation=", "path2Filter="])
        except getopt.GetoptError:
            usage(2)
        for opt, arg in opts:
            if opt in ("-o", "--operation"):
                ops = arg
            elif opt in ("-p", "--path2Filter"):
                path2filter = arg
            elif opt in ("-f", "--folderwatchhomepath"):
                fwBPath = arg
            elif opt in ("-v", "--verbose"):
                verbose = True
            
    else:
        try:
            opts, args = getopt.getopt(argv,"hf:b:m:c:i:g:ve",["folderwatchhomepath=", "monitorPath="])
        except getopt.GetoptError:
            usage(2)
        for opt, arg in opts:
            if opt == '-h':
                usage(0)
            elif opt in ("-f", "--folderwatchomepath"):
                fwBPath = arg
            elif opt in ("-m", "--monitoraPth"):
                monitorPath = arg
            elif opt in ("-c", "--configfile"):
                configFn = arg
            elif opt in ("-i", "--ignore"):
                ignores.append(arg)
            elif opt in ("-g", "--guard"):
                guards.append(arg.split('/'))
            elif opt in ("-v", "--verbose"):
                verbose = True
            elif opt in ("-e", "--extremlyverbose"):
                verbose = True
                vverbose = True


    if configFn:
        with open(configFn, 'r') as configFile:
            for line in configFile:
                line = line.rstrip()
                if len(line) > 0:
                    if line[0] == 'G':
                        guards.append(line[1:].split('/'))
                    elif line[0] == 'I':
                        ignores.append(line[1:])
                    elif line[0] == 'M':
                        if monitorPath != '':
                            print "Error: monitorPath previously set overwritten by config!"
                            sys.exit(1)
                        monitorPath = line[1:]
                    elif line[0] == 'F':
                        if fwBPath != '':
                            print "Error: folderwatchhomepath previously set overwritten by config!"
                            sys.exit(1)
                        fwBPath = line[1:]
                    else:
                        others.append(line)
    if fwBPath == '':
        fwBPath = os.path.join(os.path.expanduser("~"), ".folderwatch")

    if query:
        queryDb(fwBPath, ops, path2filter)

    fileRepoRunTime = now.strftime("%Y-%m-%d__%H%M%S")
    fwPath = os.path.join(fwBPath, os.path.abspath(monitorPath).replace('/','_'))
    dbPath = os.path.join(fwPath,'fw.db')
    actionsPath = os.path.join(fwPath, 'actions_' + fileRepoRunTime)
    violationsPath = os.path.join(fwPath, 'violations_' + fileRepoRunTime)
    cfgPath = os.path.join(fwPath, 'fw.cfg')

    if verbose:
        print "Starting folderwatch with the following configuration:"
        print "-----------------------------------------------------"
        print "fwHome:  " + fwPath
        print "monitor: " + monitorPath
        if len(guards) > 0:
            print "guards:  " + '/'.join(guards[0])
            for g in guards[1:]:
                print("         " + '/'.join(g))
        else:
            print "guards:  --default(add only)--" 
        if len(ignores) > 0:
            print "ignores: " + ignores[0]
            for i in ignores[1:]:
                print("         " + i)
        else:
            print "ignores: --not set--"
        print "-----------------------------------------------------"


    if not os.path.exists(fwPath):
        os.makedirs(fwPath)

    if os.path.exists(cfgPath):
        shutil.move(cfgPath, cfgPath + '_before_' + fileRepoRunTime) 

    with open(cfgPath, 'w') as cfgFile:
        for o in others:
           cfgFile.write(o)
        cfgFile.write('F' + fwBPath + '\n')
        cfgFile.write('M' + monitorPath + '\n')
        for g in guards:
            cfgFile.write('G' + '/'.join(g) + '\n')
        for i in ignores:
            cfgFile.write('I' + i + '\n')

    readDb(dbPath)
        
                    
    for subdir, dirs, files in os.walk(monitorPath):
        subdir = subdir[len(monitorPath)+1:]
        for fn in files:
            fpath = os.path.join(subdir,fn)
            ignore = False
            for i in ignores:
               if i in fpath:
                  ignore = True
                  break
            if ignore: 
               continue
            fid, size = getcrc(os.path.join(monitorPath,fpath)) 
            key = fid + '_' + fn
            
            if key in fileRepo: 
                f = fileRepo[key]
                pathIndex = f.pathes.index(fpath)
                if pathIndex < 0:
                    news.append(newkey(key, fpath, size, 'n'))
                else:
                    f.pathes.account(pathIndex)
                    fileRepo[key] = f 
            else: # Just add new file to repo db
                news.append(newkey(key, fpath, size, 'n'))
    
    #find unaccounted:
    for k, f in fileRepo.iteritems():
        for path in f.pathes.filter(False):
            if f.op != 'e' and f.op != 'd':
                badpathes[path] = k

    for n in news:
        if not n.key in fileRepo:
            fileRepo[n.key] = fentry(n.size, 'n', fileRepoRunTime, [n.path])
        else:
            f = fileRepo[n.key]
            f.pathes.add(n.path, True)
            f.run = fileRepoRunTime
            fileRepo[n.key] = f  
        newpathes[n.path] = n.key


    #--added
    #-----double (done)
    #-----evolved (done)
    #-----new (done)
    #-----moved (done)
    #-----readded (done)
    #--deleted
    #-----evolved (same as added evolved)
    #-----deleted (done)
    #-----moved   (same as added moved) (done)
    #--stable

    violations = []
    actions = []

    if os.path.exists(dbPath):
        shutil.move(dbPath, dbPath + '_before_' + fileRepoRunTime) 

    with open(dbPath, 'w') as dbFile:
        for k, f in sorted(fileRepo.iteritems(), key=operator.itemgetter(1)):
            accexists = f.accountedFileExists()
            unaccexists = f.accountedFileExists(False)
            if f.op == 'd':
                if accexists:
                    if unaccexists:
                        actions.append('...ReAdded: ' + pPs(f.pathes.filter(True)) + ' --- PrevLoc(s): ' + pPs(f.pathes.filter(False)))
                    else:
                        actions.append('...ReAdded: ' + pPs(f.pathes.filter(True)))
                    f.op = 'r'
                    f.run = fileRepoRunTime 
                dbFile.write(f.toline(k))
            elif f.op == 'e':
                if accexists:
                    if unaccexists:
                        actions.append('..Restored: ' + pPs(f.pathes.filter(True)) + ' --- PrevLoc(s): ' + pPs(f.pathes.filter(False)))
                    else:
                        actions.append('..Restored: ' + pPs(f.pathes.filter(True)))
                    f.op = 'r'
                    f.run = fileRepoRunTime
                dbFile.write(f.toline(k))
            else:
                evs = []
                dels = []
                added = []
                stable = []
                bEvs = False
                mDels = False
                for path in f.pathes.filter(False):
                    if path in newpathes: 
                        evs.append(path)
                    else:
                        dels.append(path)
                for path in f.pathes.filter(True):
                    if path in newpathes: 
                        if path not in badpathes:
                            #pathes which are in badpathes will be accounted already
                            added.append(path)
                    else:
                        stable.append(path)

                if len(dels) > 0:
                    #ony write delete, if no new file was created, otherwise moved
                    if len(added) == 0:
                        if accexists:
                            actions.append('...Deleted: ' + pPs(dels)  + ' --- Backup: ' + pPs(f.pathes.filter(True)))
                        else:
                            actions.append('...Deleted: ' + pPs(dels))
                        f.run = fileRepoRunTime
                        f.op = 'd'
                
                if len(evs) > 0: 
                    if accexists:
                        actions.append('...Evolved: ' + pPs(evs) + ' --- Backup: ' + pPs(f.pathes.filter(True)))
                        bEvs = True
                    else:
                        actions.append('...Evolved: ' + pPs(evs))
                    f.run = fileRepoRunTime
                    f.op = 'e'

                if len(added) > 0:
                    if unaccexists:
                        actions.append('.....Moved: ' + pPs(added) + ' --- From: ' + pPs(f.pathes.filter(False)))
                        mDels = True
                        f.op = 'm'
                    else:
                        if len(stable) > 0:
                            actions.append('...Doubled: ' + pPs(added) + ' --- Existing: ' + pPs(stable))
                        else:
                            actions.append('.....Added: ' + pPs(added))
                        f.op = 'n'
                    f.run = fileRepoRunTime
                if vverbose and len(stable) > 0 and not unaccexists and len(added) == 0:
                    print('....Stable: ' + pPs(stable))
                dbFile.write(f.toline(k))
                if f.run == fileRepoRunTime:
                    violations += guardcheck(evs, dels, added, bEvs, mDels)
    
    with open(violationsPath, 'w') as vFile:
        for v in violations:
            vstr = '.VIOLATION: #' + v[1] + '# (' + v[0] + '/' + v[2] + ')' 
            if verbose:
                print vstr
            vFile.write(vstr + '\n')
            
    with open(actionsPath, 'w') as aFile:
        for a in actions:
            if verbose:
                print a
            aFile.write(a + '\n')

if __name__ == "__main__":
	main(sys.argv[1:])


