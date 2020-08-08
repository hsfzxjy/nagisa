import re
import sys
import unittest
import importlib


class ReloadModuleTestCase(unittest.TestCase):
    drop_modules = []
    attach = []

    def setUp(self):
        drop_modules = [re.compile(x) for x in self.drop_modules]
        for mod_name in list(sys.modules):
            if any(x.match(mod_name) is not None for x in drop_modules):
                del sys.modules[mod_name]

            for attr_name, spec in self.attach:
                if ':' in spec:
                    mod_path, _, obj_name = spec.partition(':')
                else:
                    mod_path = spec
                    obj_name = None
                mod = importlib.import_module(mod_path)
                obj = mod if obj_name is None else getattr(mod, obj_name)
                setattr(self, attr_name, obj)
