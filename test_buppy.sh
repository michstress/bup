#!/opt/bin/bash


function execute_buppy { 
    sleep 1
    ($1)
    if [ -e "dest/snapLastDiffCpComp.tar.gz.enc" ]; then
        openssl enc -aes-256-cbc -d -in dest/snapLastDiffCpComp.tar.gz.enc -out decoded_Comp.tar.gz -k TheSecretKey
    fi
    if [ -e "dest/snapLastDiffCpUncomp.tar.enc" ]; then
        openssl enc -aes-256-cbc -d -in dest/snapLastDiffCpUncomp.tar.enc -out decoded_Uncomp.tar -k TheSecretKey
    fi
    echo "-------------------------------------------------------------------"
    echo "-------------------------------------------------------------------"
    echo "-----dest containing copy of src via hard links: ------------------"
    ls -l dest/snapLastHlCp/
    if [ -e "dest/snapLastDiffCpComp.tar.gz" ]; then
        echo "-----archive with files that differed to last backup (Comp): ------"
        tar -tf dest/snapLastDiffCpComp.tar.gz
    else
        echo "No snapLastDiffCpComp.tar.gz found."
    fi
    if [ -e "dest/snapLastDiffCpUncomp.tar" ]; then
        echo "-----archive with files that differed to last backup (UnComp): ----"
        tar -tf dest/snapLastDiffCpUncomp.tar
    else
        echo "No snapLastDiffCpUncomp.tar found."
    fi
    if [ -e "decoded_Comp.tar.gz" ]; then
        echo "-----decrypted (Comp): --------------------------------------------"
        tar -tf decoded_Comp.tar.gz
        rm decoded_Comp.tar.gz
    else
        echo "No decoded_Comp.tar.gz found."
    fi
    if [ -e "decoded_Uncomp.tar" ]; then
        echo "-----decrypted (UnComp): ------------------------------------------"
        tar -tf decoded_Uncomp.tar
        rm decoded_Uncomp.tar
    else
        echo "No decoded_Uncomp.tar found."
    fi
}

mkdir test_buppy
cd "test_buppy"

export PYTHONPATH=.
echo '#!/usr/bin/python' > bup_config.py
echo 'def getDoNotCompress():' >> bup_config.py
echo '    return [".mp3",".7z",".zip",".gz","jpeg","jpg","gif","dng","png","avi","mpeg","mov","wmv","mp4"]' >> bup_config.py
echo 'def getExcludeDirs():' >> bup_config.py
echo '    return ["/i1dir", "/i2dir" ]' >> bup_config.py

#ln -sf `dirname $1`/bup_config.py bup_config.py

cwd=`pwd`
cmd1="$1 -s $cwd/src -d $cwd/dest"
cmd2="$1 -s $cwd/src -d $cwd/dest -t $cwd/usb4targz"
cmd3="$1 -s $cwd/src -d $cwd/dest -t $cwd/usb4targz -c $cwd/cloudsync -k TheSecretKey"

mkdir src
mkdir dest
mkdir usb4targz
mkdir cloudsync

mkdir src/adir
echo a > src/adir/a.txt
mkdir src/bdir
echo b > src/bdir/b.txt

execute_buppy "$cmd1"

mkdir src/cdir
echo c > src/cdir/c.txt
echo c > src/cdir/c.mp3

mkdir src/i1dir
echo i > src/i1dir/i.txt
mkdir src/i2dir
echo i > src/i2dir/i.txt

execute_buppy "$cmd2"

mkdir src/ddir
echo d > src/ddir/d.txt
echo d > src/ddir/d.mp3
echo d > src/ddir/d.MOV
rm -r src/adir

execute_buppy "$cmd3"






