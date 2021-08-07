# ConfigAsCode
    Manage "Codified Norms" and "Config as Code"
## install codifiednorms
### update pip and setuptools packages
    python3 -m pip install --upgrade pip setuptools
### clone source and install from local drive
    git clone https://github.com/vikasmunshi/ConfigAsCode.git
    cd ConfigAsCode
    python3 -m pip install -e .
### pip install (<u>recommended</u>)
    python3 -m pip install -e git+https://github.com/vikasmunshi/ConfigAsCode.git#egg=codifiednorms
## usage
    cd <repository directory>
    python3 [-I] -m codifiednorms [-h] [-v] [action] [policy_type]

    positional arguments:
      action       
                   choices are ['list', 'check', 'fix', 'new']
                   list: list policies in current repository
                   check: check policies in current repository
                   fix: fix policies in current repository
                   new: create new policy
                   default action is list
      policy_type  
                   choices are ['all', 'Policy', 'PolicySet', 'Config']
                   default policy_type is all
                   ignored for "action=fix"
    
    optional arguments:
      -h, --help   show this help message and exit
      -v, --version  print version
