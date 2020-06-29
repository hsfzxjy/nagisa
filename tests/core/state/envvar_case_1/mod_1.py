from nagisa.core.state.envvar import option

envop = option


def func():
    a = option("mod_1_foo_1", T=int)
    a = option("mod_1_foo_2", T=float, default=1.0)
    a = option("mod_1_foo_3", T=str)
    a = option("mod_1_foo_4", T=[bool])

    if envop("mod_1_foo_5", T=bool, default=True):
        pass
