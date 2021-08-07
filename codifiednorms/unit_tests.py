from dataclasses import FrozenInstanceError
from functools import reduce
from itertools import groupby
from pathlib import Path
from unittest import TestCase, main

from freezer import FrozenDict
from policy import BasePolicy, Policy, PolicySet, ls_repo

b1 = BasePolicy.from_dict(dict(name='test base policy 0', version='1', doc='test doc 1',
                               target='https=//test.com', namespace='test', type='BasePolicy'))
BasePolicy.register(b1)
p1 = Policy.from_dict(dict(name='test1', version='1', doc='doc', target='test', namespace='test', type='Policy',
                           allowed={'param1': ['val1', 'val2']},
                           blocked={'param1': ['val0']},
                           enforced={}, required=tuple(), possible=tuple()))
Policy.register(p1)
p2 = Policy.from_dict(dict(name='test2', version='1', doc='doc', target='test', namespace='test', type='Policy',
                           allowed={'param0': ['val0'], 'param1': ['val2']},
                           blocked={'param1': ['val0', 'val1']},
                           enforced={}, required=tuple(), possible=tuple()))
Policy.register(p2)
p3 = Policy.from_dict(dict(name='test3', version='1', doc='doc', target='other_test', namespace='test',
                           type='Policy',
                           allowed={'param0': ['val0'], 'param1': ['val2']},
                           blocked={'param1': ['val0', 'val1']},
                           enforced={}, required=tuple(), possible=tuple()))
Policy.register(p3)
e1 = Policy.from_dict(dict(name='test', version='1', doc='doc', target='test', namespace='test',
                           type='Policy', allowed={'param1': ['val0']}))
Policy.register(e1)
ps1 = PolicySet.from_dict(dict(name='testps', version='1', doc='doc', target='test', namespace='test',
                               type='PolicySet', policies=(p1.id, p2.id), exemptions=(e1.id,)))
PolicySet.register(ps1)
ps2 = PolicySet.from_dict(dict(name='testps', version='1', doc='doc', target='test', namespace='test',
                               type='PolicySet', policies=(p1.id, p2.id), exemptions=tuple()))
PolicySet.register(ps2)


class ConfigAsCodeTests(TestCase):
    def test_Repository(self):
        for file in ls_repo(Path(__file__).parent.parent.joinpath('repository')):
            self.assertIsInstance(file, Path)
            self.assertTrue(file.exists())

    def test_PolicyRepo(self):
        self.assertEqual(b1, BasePolicy.get(b1.id))
        for policy in (p1, p2, p3, e1):
            self.assertEqual(policy, Policy.get(policy.id))
            self.assertEqual(Policy.get(policy.id).id, policy.id)

    def test_BasePolicy(self):
        self.assertGreater(len(BasePolicy.get_cached_repo()), 0)
        for pid, policy in BasePolicy.get_cached_repo().items():
            self.assertIsInstance(policy, BasePolicy)
            self.assertEqual(policy, BasePolicy.get(pid))

    def test_BasePolicyImmutability(self):
        policy = BasePolicy(name='test', version='1', doc='documentation', target='test', namespace='test',
                            type='BasePolicy')

        def change_name():
            # noinspection PyDataclass
            policy.name = 'new'

        def change_version():
            # noinspection PyDataclass
            policy.version = 'new'

        def change_doc():
            # noinspection PyDataclass
            policy.doc = 'new'

        def change_target():
            # noinspection PyDataclass
            policy.target = 'new'

        def change_namespace():
            # noinspection PyDataclass
            policy.namespace = 'new'

        def change_type():
            # noinspection PyDataclass
            policy.type = 'new'

        for func in (change_name, change_version, change_doc, change_target, change_namespace, change_type):
            self.assertRaises(FrozenInstanceError, func)

    def test_Policy(self):
        self.assertGreater(len(Policy.get_cached_repo()), 0)
        for pid, policy in Policy.get_cached_repo().items():
            self.assertIsInstance(policy, Policy)
            self.assertEqual(policy, Policy.get(pid))

    def test_PolicyArithmetic(self):
        key = lambda i: i.target
        policies = {k: list(v) for k, v in groupby(sorted(Policy.get_cached_repo().values(), key=key), key=key)}
        for target in policies.keys():
            policy = reduce(lambda x, y: x + y, policies[target])
            self.assertIsInstance(policy, Policy)
            self.assertEqual(policy.target, target)

        added = p1 + p2
        subtracted = p1 - e1
        for param, expected in (('param0', ('val0',)), ('param1', ('val2',))):
            self.assertSetEqual(set(added.allowed[param]), set(expected))
        for param, expected in (('param1', ('val0', 'val1')),):
            self.assertSetEqual(set(added.blocked[param]), set(expected))
        for param, expected in (('param1', ('val0', 'val1', 'val2')),):
            self.assertSetEqual(set(subtracted.allowed[param]), set(expected))

    def test_PolicyArithmeticErrors(self):
        self.assertRaises(TypeError, lambda: p2 + p3)
        self.assertRaises(ValueError, lambda: p1 - p2)

    def test_PolicySet(self):
        for param, expected in (('param1', ('val0', 'val2')),):
            self.assertSetEqual(set(ps1.policy[p1.target].allowed[param]), set(expected))

    def test_PolicyImmutability(self):
        def assign_dict():
            # noinspection PyTypeChecker
            Policy(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                   allowed={'param1': ['val1']},
                   blocked={'param1': ['val0']},
                   enforced={},
                   required=tuple(), possible=tuple())

        def assign_list():
            # noinspection PyTypeChecker
            Policy(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                   allowed=FrozenDict({'param1': ['val1']}),
                   blocked=FrozenDict({'param1': ['val0']}),
                   enforced=FrozenDict({}),
                   required=[], possible=[])

        def assign_str():
            # noinspection PyTypeChecker
            Policy(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                   allowed=FrozenDict({'param1': 'val1'}),
                   blocked=FrozenDict({'param1': 'val0'}),
                   enforced=FrozenDict({}),
                   required=[], possible=[])

        policy = Policy(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                        allowed=FrozenDict({'param1': ['val1']}),
                        blocked=FrozenDict({'param1': ['val0']}),
                        enforced=FrozenDict({}),
                        required=tuple(), possible=tuple())

        def assign_allowed():
            policy.allowed['param1'] += ('val2',)

        def assign_blocked():
            policy.blocked['param1'] = ('val2',)

        def assign_enforced():
            policy.enforced.update({'some': 'thing'})

        def del_key():
            policy.blocked.pop('param1')

        for func in (assign_dict, assign_list, assign_str, assign_allowed, assign_blocked,
                     assign_enforced, del_key):
            self.assertRaises(TypeError, func)

    def test_PolicyConsistency(self):
        def allowed_and_blocked():
            Policy.from_dict(dict(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                                  allowed={'param1': ['val0', 'val1']}, blocked={'param1': ['val0']},
                                  enforced={}, required=tuple(), possible=tuple()))

        def enforced_and_blocked():
            Policy.from_dict(dict(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                                  allowed={'param1': ['val1']}, blocked={'param1': ['val0']},
                                  enforced={'param1': 'val0'}, required=tuple(), possible=tuple()))

        def allowed_not_in_possible():
            Policy.from_dict(dict(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                                  allowed={'param1': ['val1']}, blocked={'param1': ['val0']},
                                  enforced={'param1': 'val0'}, required=tuple(), possible=('param0', 'param2')))

        def required_not_in_possible():
            Policy.from_dict(dict(name='test', version='1', doc='doc', target='test', namespace='test', type='Policy',
                                  allowed={'param1': ['val1']}, blocked={'param1': ['val0']},
                                  enforced={'param1': 'val0'},
                                  required=('param0', 'param1'), possible=('param1', 'param2')))

        for func in (allowed_and_blocked, enforced_and_blocked, allowed_not_in_possible, required_not_in_possible):
            self.assertRaises(ValueError, func)

    def test_PolicyErrors(self):
        # noinspection PyTypeChecker
        self.assertRaises(TypeError, lambda: p1 + ps1)


if __name__ == '__main__':
    main()
