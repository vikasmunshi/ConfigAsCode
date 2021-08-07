# ConfigAsCode

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
    usage: python3 -m codifiednorms [-h] [action] [policy_type] [path]
    
    Manage "Codified Norms" and "Config as Code"
    
    positional arguments:
      action       list: list policies in current repository (default)
                   check: check policies in current repository
                   fix: fix policies in current repository
                   new: create new policy
      policy_type  Policy (default)
                   PolicySet
                   Config
      path         path to repository folder (default current folder)
                   with "action=new" filename to save (default policy.json)
    
    optional arguments:
      -h, --help   show this help message and exit
