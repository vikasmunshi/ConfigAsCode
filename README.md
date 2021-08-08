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

    create a folder named "repository" anywhere on your local disk or clone/download a '*policy repository*'

## Usage

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

## Policy Arithmetic

Codified Norm is a set of restrictions applied on the value of a parameter. It is the translation of all applicable
policies to create a single unambiguous policy related to the valid (allowed) and invalid (blocked) values that may be
assigned to the parameter. Without policy, parameter may be assigned any possible value. A Codified Norm restricts this
to:

1. A value from within a set of **allowed** possible values, and/or
2. A value that is not in another set of **blocked** values, and/or
3. A specific value that is **enforced**, and/or
4. A restriction that a value is **required** i.e. the parameter must have a value, and/or
5. A restriction on the **possible** parameters that can be defined.

### Codified Norm

The unit of a Codified Norm is a parameter. The most basic norm is a statement of allowed and blocked values for one
parameter:

    "allowed": {"param": [ "allowed value 1", "allowed value 2", "allowed value 3", ... ] },
    "blocked": { "param": [ "blocked value 1", "blocked value 2", ... ] },

### Policy

Policy is a collection of codified norms for a set of parameters related to a specific configuration target.

    "target": "https://my-console.my-application/admin",
    
    "allowed": {"param1": [ "val11", "val12", "val16" ] },
    "blocked": { "param1": [ "val10" ] },
    "enforced": { "param3": "val31" },
    "required": ["param2"],
    "possible": [ "param1", "param2", "param3" ],

In the example above, "my-application" has three possible parameters: param1, param2, and param3. Of these, param1 may
be assigned any one of the three allowed values val11, val12 or val16 but not value val10 (blocked). Also, it is not
necessary (required) to actually assign any value to param1. However, it is required to assign a value to param2 but as
there are no restrictions (allowed or blocked) on its value it can be assigned any possible value. The value of param3
is enforced to val31. So it can only be assigned val31, and it has to be assigned.

Another policy for the same application may specify other restrictions.

    "target": "https://my-console.my-application/admin",
    
    "allowed": {"param1": [ "val11", "val12" ], "param2": [ "val21", "val22" ],  },
    "blocked": { "param2": [ "val20" ] },
    "enforced": {},
    "required": [],
    "possible": [ "param1", "param2", "param3" ],

To apply both the policies the assigned values must adhere to the restrictions of both the policies. The combined
restrictions after applying both the policies is the addition of the two policies. In this example the addition results
are:

    "target": "https://my-console.my-application/admin",
    
    "allowed": {"param1": [ "val11", "val12" ], "param2": [ "val21", "val22" ],  },
    "blocked": { "param1": [ "val10" ], "param2": [ "val20" ] },
    "enforced": {"param3": "val31" },
    "required": ["param2"],
    "possible": [ "param1", "param2", "param3" ],

val16 is allowed for param1 by the first policy but not the second, and therefore it is not allowed by the sum of the
two policies.

#### Policy addition

Policy addition is the composition of restrictions imposed by two policies.

    P = P1 + P2
    => P[allowed][param] = Intersection( P1[allowed][param], P2[allowed][param] )
        if both are P1[allowed] and P2[allowed] define restrictions for param,
        otherwise P1[allowed][param] or P2[allowed][param] depending on which is defined
        computationally, this is the same as:-
        Intersection( (P1[allowed][param] OR P2[allowed][param]), (P2[allowed][param] OR P1[allowed][param]) )

    => P[blocked][param] = Union( P1[blocked][param], P2[blocked][param] )
    => P[enforced] = Update( P1[enforced], P2[enforced] )
        note: both policies cannot enforce different values for the same parameter!
    => P[required] = P1[required] + P2[required]
    => P[possible] = Intersection( P1[possible], P2[possible])

In code policy addition (plus some consistency checks) is:

    def intersection(l1, l2): return tuple(set(l1 or l2).intersection(set(l2 or l1)))
    def union(l1, l2): return tuple(set(l1).union(set(l2)))
    def __add__(self, other):
        allowed={param: intersection(self.allowed.get(param, []), other.allowed.get(param, []))
                        for param in union(self.allowed.keys(), other.allowed.keys())},
        blocked={param: union(self.blocked.get(param, []), other.blocked.get(param, []))
                        for param in union(self.blocked.keys(), other.blocked.keys())},
        enforced=dict(other.enforced, **self.enforced),
        required=union(self.required, other.required),
        possible=intersection(self.possible, other.possible)

#### Policy subtraction

Policy subtraction is the easing (exemption) of restrictions of some policy by what is allowed by another policy.

    P = P1 - P2
    => P[allowed][param] = Union( P1[allowed][param], P2[allowed][param] )
    => P[blocked][param] = P1[blocked][param] - P2[allowed][param]
    => P[enforced] = Delete( P1[enforced], P2[allowed] )
    => P[required] = P1[required] - P2[allowed]
    => P[possible] = No restrictions if none in P1 otherwise Union( P1[possible], P2[allowed])

In code policy subtraction (plus some consistency checks) is:

    def __sub__(self, other):
    allowed={param: union(self.allowed.get(param, []), other.allowed.get(param, []))
                    for param in union(self.allowed.keys(), other.allowed.keys())},
    blocked={param: tuple(set(values) - set(other.allowed.get(param, [])))
                    for param, values in self.blocked.items()},
    enforced={param: value for param, value in self.enforced.items() if value not in other.allowed.get(param)},
    required=tuple(set(self.required) - set(other.allowed.keys())),
    possible=tuple() if not self.possible else union(self.possible, other.allowed.keys())))

### PolicySet

PolicySet is a collection of policies (and exemptions) which are related to a one or more targets.

    class PolicySet(BasePolicy):
        policies: typing.Tuple[str, ...]
        exemptions: typing.Tuple[str, ...]
    
    e.g:
    "policies": [
        "policies.test:e48001c4-28b1-538f-b73f-58e77dfeafe1",
        "policies.test:a7ff3ef9-1634-5ecf-bc91-66ea0d8b475e"
    ],
    "exemptions": [
        "policies.test:cdb7f4c1-bad8-582b-a2aa-68b32e9e8560"
    ],

The effective policy per target in a PolicySet is computed by repeated addition of all policies for that target followed
by subtraction of all exemptions.

    policy = { target: reduce(lambda x, y: x - y, exemptions.get(target, []), functools.reduce(lambda x, y: x + y, policies[target]))
                for target in policies.keys() }

Addition of PolicySets is per target addition of effective Policy

    def __add__(self, other):
        return {target: self.policy[target] + other.policy[target] if (target in self.policy and target in other.policy) else (self.policy.get(target) or other.policy[target])
                    for target in union(self.policy.keys(), other.policy.keys())}

Subtraction of PolicySets is per target subtraction of effective Policy

    def __sub__(self, other):
        return {target: policy - other.policy[target] if target in other.policy else policy
                    for target, policy in self.policy.items()}

### Config

Config is the specification of actual assignments along with the applicable policy (Policy or PolicySet).

    "assigned": {
                    "https://my-console.my-application/admin": { "param11": "val99" }
                },
    "applicable": "policies.test:b1be792e-7e22-5fbc-b12f-b5b589b8cc7e",

Config can be checked for (policy) inconsistencies and policy_violations and generate target configuration (as code).