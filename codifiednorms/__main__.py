#!/usr/bin/env python3.9
# -*- coding: utf-8 -*-
"""
Cmdline interface
"""
from .policy import *


@enforce_strict_types
def list_repo(policy_class: type) -> None:
    for policy_type in (policy_class, *policy_class.__subclasses__()):
        for _, policy in policy_type.get_cached_repo().items():
            print(f'{policy.id} {policy.type} "{policy.proper_name}"')


@enforce_strict_types
def check_repo(policy_class: type) -> None:
    for file in ls_repo():
        try:
            with open(file) as in_file:
                policy = policy_class.subclass_from_dict(dict(json.load(in_file), **{'namespace': ns(file)}))
            if policy is None:
                print(f'NOK {file.relative_to(repo_root)} "corrupted or not a policy"')
                continue
            if policy.is_empty:
                print(f'NOK {file.relative_to(repo_root)} {policy.id} "is empty"')
                continue
            if not policy.as_dict:
                print(f'NOK {file.relative_to(repo_root)} {policy.id} "cannot be dumped"')
                continue
            if hasattr(policy, 'inconsistencies') and (errors := policy.inconsistencies) != '':
                print(f'NOK {file.relative_to(repo_root)} {policy.id} "has consistency errors {errors}"')
                continue
            if hasattr(policy, 'policy_violations') and (errors := policy.policy_violations) != '':
                print(f'NOK {file.relative_to(repo_root)} {policy.id} "has policy violations {errors}"')
                continue
            if hasattr(policy, 'policy'):
                if not policy.policy:
                    print(f'NOK {file.relative_to(repo_root)} {policy.id} "empty policy"')
                    continue
                if hasattr(policy.policy, 'inconsistencies') and (errors := policy.policy.inconsistencies) != '':
                    print(f'NOK {file.relative_to(repo_root)} {policy.id}'
                          f' "has consistency errors in derived policy {policy.policy.id} {errors}"')
                    continue
        except (IOError, json.JSONDecodeError, UnicodeDecodeError):
            print(f'NOK {file.relative_to(repo_root)} "corrupted or not a policy"')
        except (KeyError, ValueError) as e:
            print(f'NOK {file.relative_to(repo_root)} "policy has errors"\n\t{e}')


@enforce_strict_types
def fix_repo(policy_class: type) -> None:
    update_log = repo_root.joinpath('updates')
    if update_log.exists():
        with open(update_log) as in_file:
            updated = json.load(in_file)

    else:
        updated = {}
    policy_repos = {c.__name__: [] for c in (BasePolicy, *BasePolicy.__subclasses__())}
    for file in ls_repo():
        try:
            with open(file) as in_file:
                policy_data = json.load(in_file)
                policy = BasePolicy.subclass_from_dict(dict(policy_data, **{'namespace': ns(file)}))
            if isinstance(policy, BasePolicy):
                policy_repos[policy.__class__.__name__] += [(file, policy_data, policy)]
        except (IOError, json.JSONDecodeError, KeyError, UnicodeDecodeError):
            pass

    def update(file: pathlib.Path, policy_data: dict, policy: BasePolicy) -> None:
        if (old_id := policy_data.get('id')) != policy.id or policy_data.get('namespace') != policy.namespace:
            policy.dump(file)
            print(f'updated policy file "{file.relative_to(repo_root)}"', end=' ')
            if old_id:
                updated.pop(policy.id, None)
                updated[old_id] = policy.id
                print(f'id "{old_id}" -> "{policy.id}"')
            else:
                print(f'file "{file.relative_to(repo_root)}" -> "{policy.id}"')

    for file, policy_data, policy in policy_repos['BasePolicy'] + policy_repos['Policy']:
        update(file, policy_data, policy)
    for file, policy_data, policy in policy_repos['PolicySet']:
        if any(pid in updated for pid in policy.policies + policy.exemptions):
            policy = PolicySet.from_dict(
                dict(policy_data, **{'policies': tuple(updated.get(p, p) for p in policy.policies),
                                     'exemptions': tuple(updated.get(p, p) for p in policy.exemptions)}))
        update(file, policy_data, policy)
    for file, policy_data, policy in policy_repos['Config']:
        if policy.applicable in updated:
            policy = Config.from_dict(
                dict(policy_data, **{'applicable': updated.get(policy.applicable, policy.applicable)}))
        update(file, policy_data, policy)
    with open(update_log, 'w') as out_file:
        json.dump(updated, out_file, indent=4)


@enforce_types
def create_new(policy_class: type) -> None:
    ts = str(int(time.time()))
    path = pathlib.Path(os.getcwd()).joinpath(f'{policy_class.__name__}_{ts}.json')
    if repo_root in path.parents:
        policy = policy_class.from_dict(dict(namespace=ns(path), type=policy_class.__name__))
        policy.dump(path)
        print(f'created empty {policy_class.__name__} "{policy.id}" and saved as "{path.relative_to(repo_root)}"')
    else:
        print(f'current directory {os.getcwd()} does not appear to be in a policy repository')


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
        from .__init__ import __package__, __version__

        print(f'{__package__}-{__version__}')
    else:
        funcs[args.action](policy_class=policy_types[args.policy_type])
