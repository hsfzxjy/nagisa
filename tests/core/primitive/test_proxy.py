import unittest
from nagisa.core.primitive.proxy import proxy, SwitchableList


class TestProxy(unittest.TestCase):
    def test_proxy_ordinary_object(self):
        cases = [
            42,
            42.,
            'foo',
            True,
            (),
            (42, ),
        ]

        for case in cases:
            self.assertIs(proxy(case), case)

    def test_proxy_list(self):
        lst = [42]
        self.assertIsInstance(proxy(lst, T=[int]), SwitchableList)

    def test_proxy_proxy(self):
        lst = proxy([42], T=[int])
        self.assertIs(lst, proxy(lst))


class TestSwitchableList(unittest.TestCase):
    def test_subclass(self):
        self.assertTrue(isinstance(proxy([42], T=[int]), list))

    def test_host_none(self):
        lst = proxy([42], T=[int], mutable=False)
        self.assertRaises(RuntimeError, lst.append, 42)
        lst.mutable(True)
        lst.append(42)
        self.assertEqual(lst, [42, 42])
        lst.mutable(False)
        self.assertRaises(RuntimeError, lst.append, 42)

    def test_host_obj(self):
        class C:
            def mutate(self, lst, value):
                lst.mutable(value)

        c = C()
        lst = proxy([42], T=[int], host=c)
        self.assertRaises(RuntimeError, lst.append, 42)
        self.assertRaises(RuntimeError, lst.mutable, True)
        c.mutate(lst, True)
        lst.append(42)
        self.assertEqual(lst, [42, 42])
        del c
        with self.assertRaises(RuntimeError) as cm:
            lst.mutable(False)
        self.assertEqual(str(cm.exception), 'Host has been freed')


class TestImmutableList(unittest.TestCase):
    def test_fail(self):
        lst = proxy([1, 2, 3], T=[int])
        cases = [
            'del lst[0]',
            'lst += [42]',
            'lst *= 4',
            'lst[0]=42',
            'lst[0]*=42',
            'lst.clear()',
            'lst.pop(0)',
            'lst.reverse()',
            'lst.sort()',
            'lst.append(42)',
            'lst.extend([42])',
            'lst.insert(0, 42)',
        ]

        for stmt in cases:
            with self.assertRaises(RuntimeError,
                                   msg=f'{stmt!r} should failed'):
                exec(stmt)

    def test_valid(self):
        import sys, pickle
        lst = proxy([1, 2, 3], T=[int])
        cases = [
            ['lst + [4]', [1, 2, 3, 4]],
            ['1 in lst', True],
            ['lst==[1,2,3]', True],
            # __format__ ignored
            ['lst >= [0, 1, 3]', True],
            ['hash(lst)', TypeError],
            ['iter(lst)', ...],
            ['lst <= [1, 3, 4]', True],
            ['len(lst)', 3],
            ['lst < [2, 2, 4]', True],
            ['lst * 4', [1, 2, 3] * 4],
            ['lst != [1,2,4]', True],
            ['pickle.dumps(lst, protocol=0)', TypeError],
            ['pickle.dumps(lst, protocol=1)', TypeError],
            ['repr(lst)', repr([1, 2, 3])],
            ['list(reversed(lst))', [3, 2, 1]],
            ['4 * lst', [1, 2, 3] * 4],
            ['sys.getsizeof(lst)',
             sys.getsizeof([1, 2, 3])],
            ['str(lst)', str([1, 2, 3])],
            ['lst.copy()', [1, 2, 3]],
            ['lst.count(1)', 1],
            ['lst.index(3)', 2],
        ]
        for expr, expected in cases:
            if isinstance(expected, type) and issubclass(expected, Exception):
                self.assertRaises(expected, eval, expr, msg=expr)
            else:
                result = eval(expr)
                if expected is not ...:
                    self.assertEqual(result, expected)


class TestMutableList(unittest.TestCase):
    def test_valid_mutation(self):
        cases = [
            ['del lst[0]', [3, 1]],
            ['lst += [42]', [2, 3, 1, 42]],
            ['lst *= 4', [2, 3, 1] * 4],
            ['lst[0]=42', [42, 3, 1]],
            ['lst[0]*=42', [2 * 42, 3, 1]],
            ['lst.clear()', []],
            ['lst.pop(0)', [3, 1]],
            ['lst.reverse()', [1, 3, 2]],
            ['lst.sort()', [1, 2, 3]],
            ['lst.append(42)', [2, 3, 1, 42]],
            ['lst.extend([42])', [2, 3, 1, 42]],
            ['lst.insert(0, 42)', [42, 2, 3, 1]],
        ]

        for stmt, expected in cases:
            lst = proxy([2, 3, 1], T=[int], mutable=True)
            exec(stmt)
            self.assertEqual(lst, expected, msg=stmt)

    def test_bad_type(self):
        cases = [
            'lst.append(True)',
            'lst.extend(True)',
            'lst.extend(["foo"])',
            'lst.insert(0, "foo")',
        ]

        for stmt in cases:
            lst = proxy([2, 3, 1], T=[int], mutable=True)

            with self.assertRaises(TypeError, msg=f'{stmt!r} should failed'):
                exec(stmt)

    def test_valid(self):
        import sys, pickle
        lst = proxy([1, 2, 3], T=[int], mutable=True)
        cases = [
            ['lst + [4]', [1, 2, 3, 4]],
            ['1 in lst', True],
            ['lst==[1,2,3]', True],
            # __format__ ignored
            ['lst >= [0, 1, 3]', True],
            ['hash(lst)', TypeError],
            ['iter(lst)', ...],
            ['lst <= [1, 3, 4]', True],
            ['len(lst)', 3],
            ['lst < [2, 2, 4]', True],
            ['lst * 4', [1, 2, 3] * 4],
            ['lst != [1,2,4]', True],
            ['pickle.dumps(lst, protocol=0)', TypeError],
            ['pickle.dumps(lst, protocol=1)', TypeError],
            ['repr(lst)', repr([1, 2, 3])],
            ['list(reversed(lst))', [3, 2, 1]],
            ['4 * lst', [1, 2, 3] * 4],
            ['sys.getsizeof(lst)',
             sys.getsizeof([1, 2, 3])],
            ['str(lst)', str([1, 2, 3])],
            ['lst.copy()', [1, 2, 3]],
            ['lst.count(1)', 1],
            ['lst.index(3)', 2],
        ]
        for expr, expected in cases:
            if isinstance(expected, type) and issubclass(expected, Exception):
                self.assertRaises(expected, eval, expr, msg=expr)
            else:
                result = eval(expr)
                if expected is not ...:
                    self.assertEqual(result, expected)