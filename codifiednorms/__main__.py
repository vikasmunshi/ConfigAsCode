#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
try:
    from .policy import *
except ImportError:
    from policy import *
__package__ = 'codifiednorms'
__version__ = '0.2.20210808'


@enforce_strict_types
def list_repo(policy_class: type) -> None:
    for policy_type in (policy_class, *policy_class.__subclasses__()):
        for _, policy in policy_type.get_cached_repo().items():
            print(f'{policy.id} {policy.type} "{policy.proper_name}"')


@enforce_strict_types
def check_repo(policy_class: type) -> None:
    cwd = pathlib.Path(os.getcwd())
    for file in ls_repo():
        try:
            with open(file) as in_file:
                policy = policy_class.subclass_from_dict(dict(json.load(in_file), **{'namespace': file.parent.stem}))
            if policy is None:
                print(f'NOK {file.relative_to(cwd)} "corrupted or not a policy"')
                continue
            if policy.is_empty:
                print(f'NOK {file.relative_to(cwd)} {policy.id} "is empty"')
                continue
            if not policy.as_dict:
                print(f'NOK {file.relative_to(cwd)} {policy.id} "cannot be dumped"')
                continue
            if hasattr(policy, 'is_consistent') and not policy.is_consistent:
                print(f'NOK {file.relative_to(cwd)} {policy.id} "is not consistent"')
                continue
            if hasattr(policy, 'policy') and not policy.policy:
                print(f'NOK {file.relative_to(cwd)} {policy.id} "empty policy"')
                continue
        except (IOError, json.JSONDecodeError, UnicodeDecodeError):
            print(f'NOK {file.relative_to(cwd)} "corrupted or not a policy"')
        except (KeyError, ValueError) as e:
            print(f'NOK {file.relative_to(cwd)} "policy has errors"\n\t{e}')


@enforce_strict_types
def fix_repo(policy_class: type) -> None:
    cwd = pathlib.Path(os.getcwd())
    policy_repo = {c.__name__: [] for c in (BasePolicy, *BasePolicy.__subclasses__())}
    for file in ls_repo():
        try:
            with open(file) as in_file:
                policy_data = json.load(in_file)
                policy = BasePolicy.subclass_from_dict(dict(policy_data, **{'namespace': file.parent.stem}))
            if isinstance(policy, BasePolicy):
                policy_repo[policy.__class__.__name__] += [(file, policy_data, policy)]
                policy.__class__.register(policy)
        except (IOError, json.JSONDecodeError, KeyError, UnicodeDecodeError):
            pass
    updated = {}

    def update(file: pathlib.Path, policy_data: dict, policy: BasePolicy) -> None:
        if (old_id := policy_data.get('id')) != policy.id or policy_data.get('namespace') != policy.namespace:
            policy.dump(file)
            print(f'updated policy file "{file.stem}"', end=' ')
            if old_id:
                updated[old_id] = policy.id
                print(f'id "{old_id}" -> "{policy.id}"')
            else:
                print(f'file "{file.relative_to(cwd)}" -> "{policy.id}"')

    for file, policy_data, policy in policy_repo['BasePolicy'] + policy_repo['Policy']:
        update(file, policy_data, policy)
    for file, policy_data, policy in policy_repo['PolicySet']:
        if any((pid in policy.policies) or (pid in policy.exemptions) for pid in updated.keys()):
            policy = PolicySet.from_dict(
                dict(policy_data, **{'policies': tuple(updated.get(p, p) for p in policy.policies),
                                     'exemptions': tuple(updated.get(p, p) for p in policy.exemptions)}))
        update(file, policy_data, policy)
    for file, policy_data, policy in policy_repo['Config']:
        if policy.applicable in updated:
            policy = Config.from_dict(
                dict(policy_data, **{'applicable': updated.get(policy.applicable, policy.applicable)}))
        update(file, policy_data, policy)


@enforce_types
def create_new(policy_class: type) -> None:
    ts = str(int(time.time()))
    path = pathlib.Path(os.getcwd()).joinpath(f'{policy_class.__name__}_{ts}.json')
    policy = policy_class.from_dict(dict(name='policy name here',
                                         version=f'{ts} replace with version',
                                         doc=f'https://documentation.link',
                                         target='target url or name here',
                                         namespace=path.parent.stem,
                                         type=policy_class.__name__))
    policy.dump(path)
    print(f'created new empty {policy_class.__name__} "{policy.id}" and saved as "{path.stem}"')


if __name__ == '__main__':
    import argparse

    funcs = {'list': list_repo, 'check': check_repo, 'fix': fix_repo, 'new': create_new}
    policy_types = dict({'all': BasePolicy}, **{c.__name__: c for c in BasePolicy.__subclasses__()})

    parser = argparse.ArgumentParser(description='Manage "Codified Norms" and "Config as Code"',
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     prog='python3 -m codifiednorms')
    parser.add_argument('action', default='list', metavar='action', nargs='?',
                        choices=list(funcs.keys()),
                        help=f'\nchoices are {list(funcs.keys())}\n'
                             'list: list policies in current repository\n'
                             'check: check policies in current repository\n'
                             'fix: fix policies in current repository\n'
                             'new: create new policy\n'
                             'default action is list', )
    parser.add_argument('policy_type', type=str, default='all', metavar='policy_type', nargs='?',
                        choices=list(policy_types.keys()),
                        help=f'\nchoices are {list(policy_types.keys())}\ndefault policy_type is all\n'
                             f'ignored for "action=fix"')
    parser.add_argument('-v', '--version', action='store_true', help='print version')

    args = parser.parse_args()
    if args.version:
        print(f'{__package__}-{__version__}')
    else:
        funcs[args.action](policy_class=policy_types[args.policy_type])
