#!/opt/bin/bash

function execute_updt {
    echo "------------------------------------"
    echo "$1"
    ($1)
    cat fw/_home_martin_tmp_test_fw_m/fw.db
    sleep 1
}

function create_testdirs {
    mkdir -p m/a
    mkdir -p m/b
    mkdir -p m/@eaDir
    rm -rf fw
    echo -e 'a/#++#' > c.cfg
    echo -e 'badu' > m/@eaDir/badu.txt
}

function add_files {
    for i in $1; do
        echo adding $i
        echo $i > m/a/$i.txt
    done
}

function move_files {
    for i in $1; do
        echo moving $i
        mv m/a/$i.txt  m/b/$i.txt
    done
}

function move_back {
    echo moving back
    mv m/b/* m/a
}

function edit_files {
    for i in $1; do
        echo edit $i
        echo "more" >> m/a/$i.txt 
    done
}

function remove_files {
    for i in $1; do
        echo remove $i
        rm m/a/$i.txt
    done
}

function copy_files {
    for i in $1; do 
        echo copy $i
        cp -p m/a/$i.txt m/b/$i.txt
    done
}

function remove_testdirs {
     rm m/a -rf
     rm m/b -rf
}

mkdir "test_fw"
cd "test_fw"
rm * -rf

cwd=`pwd`
cmd1="$1 -f $cwd/fw -g a/#~+# -g bogus/#### -m $cwd/m -v -i @eaDir -i notwhat"
cmd2="$1 -c fw/_home_martin_tmp_test_fw_m/fw.cfg -v"

create_testdirs
add_files "a b c d"
execute_updt "$cmd1"
add_files "e f"
execute_updt "$cmd1"
edit_files "b d"
execute_updt "$cmd2"
move_files "b c d"
execute_updt "$cmd2"
remove_files "a f"
execute_updt "$cmd2"
move_back
execute_updt "$cmd2"
copy_files "d e"
execute_updt "$cmd2"
edit_files "b d"
execute_updt "$cmd2"
#remove_testdirs

