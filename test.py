import pyflakes.checker2, pyflakes.ast as ast
from traceback import print_exc

code = [
'import fu; (1 for fu in ())',

'foo',

'def foo(bar=meep): pass',

'''@meep
def foo(): pass'''
]

code = [
'def foo(bar=meep): a, (b, c) = [([(None, fap)])]',
'a, (b, c) = [a for a in b]',
'''import foo
def bar():
    f = foo
    import foo
''',
'''
from __future__ import with_statement
with foo as bar:
    meep
''',
'''
from __future__ import with_statement
with foo:
    meep
''',
'''
global a, b
''',
'''
for a in xrange(50):
    pass
''',
'for a, b in xrange(50): pass',
'for (a, b) in xrange(50): print b',
'for x in xrange(5): print x',
'def foo(a, a): pass',
'class Foo: pass',
'from fu import *',
'del a',
'import fu; fu.bar = 1',
'f(123).f()',
'''
def f(foo):
    class C:
        bar = foo
        def f(self):
            return foo
    return C()

f(123).f()''',
'''
import fu; [fu for _ in range(1)]
''',
'''
import fu
def bar():
    def baz():
        def fu():
            pass
''',
'''
import fu
try: pass
except Exception, fu: pass
''',
'''
try: pass
except Foo, (a, b, c): pass
''',
]

print 
for codestr in code:
    print codestr

    try:
        messages = pyflakes.checker2.Checker(ast.parse(codestr)).messages
        if messages:
            for m in messages:
                print '    '+ str(m)
        else:
            print '    (no errors)'
    except:
        print_exc()
    print
    print ast.dump(ast.parse(codestr))

    print '-'*80

