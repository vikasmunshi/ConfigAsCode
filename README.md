# ConfigAsCode

    Manage "Codified Norms" and "Config as Code"

## Install

### Update packages required for install

    python3 -m pip install --upgrade pip setuptools

### Option 1: clone source and install from local drive

    git clone https://github.com/vikasmunshi/ConfigAsCode.git
    cd ConfigAsCode
    python3 -m pip install -e .

### Option 2 (<u>recommended</u>): install directly from git

    python3 -m pip install -e git+https://github.com/vikasmunshi/ConfigAsCode.git#egg=codifiednorms

### Post install

    create a folder named "**repository**" anywhere on your local disk or clone/download a '*policy repository*'

## usage

    cd <path to repository folder>
    usage: python3 [-I] -m codifiednorms [-h] [-v] [action] [policy_type]

    positional arguments:
      action       choices are ['list', 'check', 'fix', 'new']
      policy_type  choices are ['all', 'Policy', 'PolicySet', 'Config']

    examples:
    1. list all polices in the repository
        python3 -m codifiednorms
        python3 -m codifiednorms list
    2. list policies with errors (and the errors)
        python3 -m codifiednorms check
    3. update policy id (because policy content has changed) and propogate that change to other polices that reference it
        python3 -m codifiednorms fix
    4. create a new (empty) policy file in the current directory
        python3 -m codifiednorms new PolicySet

### Policy Arithmetic

Codified Norm is a set of restrictions applied on the value of a parameter. It is the translation of all applicable
policies to create a single unambiguous policy related to the valid (allowed) and invalid (blocked) values that may be
assigned to the parameter. Without policy, parameter may be assigned any possible value. A Codified Norm restricts this
to:

1. A value from within a set of **allowed** possible values, and/or
2. A value that is not in another set of **blocked** values, and/or
3. A specific value that is **enforced**, and/or
4. A restriction that a value is **required** i.e. the parameter must have a value, and/or
5. A restriction on the **possible** parameters that can be defined.

The unit of a Codified Norm is a parameter. The most basic norm is a statement of allowed and blocked values for one
parameter:

    "allowed": {"param": [ "allowed value 1", "allowed value 2", "allowed value 3", ... ] },
    "blocked": { "param": [ "blocked value 1", "blocked value 2", ... ] },

This can be extended to specifying codified norms for the set of parameters related to a specific configuration target
i.e. a Policy

    "target": "https://my-console.my-application/admin",
    
    "allowed": {"param11": [ "val11", "val12", "val16" ] },
    "blocked": { "param11": [ "val00" ] },
    "enforced": { "param13": "val13" },
    "required": ["param12"],
    "possible": [ "param11", "param12", "param13" ],

In the example above, "my-application" has three possible parameters: param11, param12, and param13. Of these, param11
may be assigned any one of the three allowed values val11, val12 or val16 but not value val00 (blocked). Also, it is not
necessary (required) to actually assign any value to param11. However, it is required to assign a value to param12 but
as there are no restrictions (allowed or blocked) on its value it can be assigned any possible value. The value of
param13 is enforced to val13. So it can only be assigned val13 and it has to be assigned.



#### policy addition

#### policy subtraction
