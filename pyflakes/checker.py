'''
improved PyFlakes using the newer _ast module
'''

# (c) 2005-2008 Divmod, Inc.
# (c) 2008 Kevin Watters
# See LICENSE file for details

import _ast
import __builtin__
from pyflakes import messages

def checkFile(filename):
    f = open(filename)
    source = f.read()
    f.close()

    return check(source, filename)

def check(source, filename='<unknown>'):
    ast = compile(source, filename, 'exec', _ast.PyCF_ONLY_AST)
    return Checker(ast, filename)

allowed_names = set(['__file__'])

def allow_undefined_name(name):
    if name in allowed_names or hasattr(__builtin__, name):
        return True

def iter_fields(node):
    """Iterate over all fields of a node, only yielding existing fields."""
    for field in node._fields or []:
        try:
            yield field, getattr(node, field)
        except AttributeError:
            pass

def iter_child_nodes(node):
    """Iterate over all child nodes or a node."""
    for name, field in iter_fields(node):
        if isinstance(field, _ast.AST):
            yield field
        elif isinstance(field, list):
            for item in field:
                if isinstance(item, _ast.AST):
                    yield item

class Binding(object):
    """
    @ivar used: pair of (L{Scope}, line-number) indicating the scope and
                line number that this binding was last used
    """
    __slots__ = ['name', 'source', 'used']

    def __init__(self, name, source):
        self.name = name
        self.source = source
        self.used = False

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<%s object %r from line %d, col %d at 0x%x>' % (self.__class__.__name__,
                                                                self.name,
                                                                self.source.lineno,
                                                                self.source.col_offset,
                                                                id(self))

class UnBinding(Binding):
    '''Created by the 'del' operator.'''

class Importation(Binding):
    def __init__(self, name, source):
        name = name.split('.')[0]
        super(Importation, self).__init__(name, source)

class Assignment(Binding):
    pass

class FunctionDefinition(Binding):
    pass

class Scope(dict):
    import_starred = False     # set to True when import * is found

    def __repr__(self):
        return '<%s at 0x%x %s>' % (self.__class__.__name__, id(self), dict.__repr__(self))

    def __init__(self):
        super(Scope, self).__init__()

    def set_used(self, name_node):
        try:
            self[name_node.id].used = (self, name_node.lineno, name_node.col_offset)
        except KeyError:
            return False
        else:
            return True

class ClassScope(Scope):
    pass

class FunctionScope(Scope):
    """
    I represent a name scope for a function.

    @ivar globals: Names declared 'global' in this function.
    """
    def __init__(self):
        super(FunctionScope, self).__init__()
        self.globals = {}

class ModuleScope(Scope):
    pass

class Checker(object):
    node_depth = 0

    def __init__(self, ast, filename='(none)'):
        self.deferred = []
        self.dead_scopes = []
        self.messages = []
        self.filename = filename
        self.scope_stack = [ModuleScope()]
        self.futures_allowed = True

        self.handle_children(ast)
        for handler, scope in self.deferred:
            self.scope_stack = scope
            handler()
        del self.scope_stack[1:]
        self.pop_scope()
        self.check_dead_scopes()

    def defer(self, callback):
        '''Schedule something to be called after just before completion.

        This is used for handling function bodies, which must be deferred
        because code later in the file might modify the global scope. When
        `callable` is called, the scope at the time this is called will be
        restored, however it will contain any new bindings added to it.
        '''
        self.deferred.append((callback, self.scope_stack[:]))

    scope = property(lambda self: self.scope_stack[-1])

    def pop_scope(self):
        self.dead_scopes.append(self.scope_stack.pop())

    def check_dead_scopes(self):
        for scope in self.dead_scopes:
            for imp in scope.itervalues():
                if isinstance(imp, Importation) and not imp.used:
                    node = imp.source
                    self.report(messages.UnusedImport, node.lineno, node.col_offset, imp.name)

    def push_function_scope(self):
        self.scope_stack.append(FunctionScope())

    def push_class_scope(self):
        self.scope_stack.append(ClassScope())

    def report(self, message_class, *args, **kwargs):
        self.messages.append(message_class(self.filename, *args, **kwargs))

    def handle_children(self, tree):
        for node in iter_child_nodes(tree):
            self.handle_node(node)

    def handle_nodes(self, nodes):
        for node in nodes:
            self.handle_node(node)
    
    def handle_node(self, node):
        self.node_depth += 1

        node_type = node.__class__.__name__.upper()
        if node_type not in ('STMT', 'IMPORTFROM'):
            self.futures_allowed = False

        try:
            handler = getattr(self, node_type)
            handler(node)
        finally:
            self.node_depth -= 1

    def ignore(self, node):
        pass

    STMT = PRINT = PRINTNL = TUPLE = LIST = ASSTUPLE = ASSATTR = \
    ASSLIST = GETATTR = SLICE = SLICEOBJ = IF = CALL = DISCARD = \
    RETURN = ADD = MOD = SUB = NOT = UNARYSUB = INVERT = ASSERT = COMPARE = \
    SUBSCRIPT = AND = OR = TRYEXCEPT = RAISE = YIELD = DICT = LEFTSHIFT = \
    RIGHTSHIFT = KEYWORD = TRYFINALLY = WHILE = EXEC = MUL = DIV = POWER = \
    FLOORDIV = BITAND = BITOR = BITXOR = LISTCOMPFOR = LISTCOMPIF = \
    AUGASSIGN = BACKQUOTE = UNARYADD = GENEXPR = GENEXPRFOR = GENEXPRIF = \
    IFEXP = handle_children

    CONST = PASS = CONTINUE = BREAK = ELLIPSIS = ignore

    # new
    ASSIGN = \
    EXPR = \
    REPR = \
    BINOP = \
    BOOLOP = \
    UNARYOP = \
    INDEX = \
    UADD = \
    EXCEPTHANDLER = \
    handle_children

    NUM = \
    STR = \
    ignore

    # wrong
    COMPREHENSION = handle_children
    ATTRIBUTE = ignore
    LOAD = ignore # always in "ctx"
    STORE = ignore



    def add_binding(self, lineno, col, value, report_redef=True):
        if (isinstance(self.scope.get(value.name), FunctionDefinition) and
            isinstance(value, FunctionDefinition)):
            self.report(messages.RedefinedFunction, lineno, col,
                value.name, self.scope[value.name].source.lineno)

        if not isinstance(self.scope, ClassScope):
            for scope in reversed(self.scope_stack):
                if (isinstance(scope.get(value.name), Importation)
                    and not scope[value.name].used
                    and report_redef):
                    self.report(messages.RedefinedWhileUnused,
                                lineno, col, value.name, scope[value.name].source.lineno)

        if isinstance(value, UnBinding):
            try:
                del self.scope[value.name]
            except KeyError:
                self.report(messages.UndefinedName, lineno, col, value.name)
        else:
            self.scope[value.name] = value

    def WITH(self, node):
        """
        Handle C{with} by adding bindings for the name or tuple of names it
        puts into scope and by continuing to tprocess the suite within the
        statement.
        """

        self.handle_node(node.context_expr)

        if isinstance(node.optional_vars, _ast.Tuple):
            with_vars = node.optional_vars.elts
        else:
            with_vars = [node.optional_vars]

        for var in with_vars:
            if var is not None:
                self.add_binding(var.lineno, var.col_offset, Assignment(var.id, var))

        self.handle_nodes(node.body)

    def GLOBAL(self, node):
        """
        Keep track of globals declarations.
        """
        if isinstance(self.scope, FunctionScope):
            self.scope.globals.update(dict.fromkeys(node.names))

    def LISTCOMP(self, node):
        self.handle_nodes(node.generators)
        self.handle_node(node.elt)

    GENERATOREXP = LISTCOMP

    def FOR(self, node):
        """
        Process bindings for loop variables.
        """
        vars = []
        def collect_loop_vars(n):
            if hasattr(n, 'id'):
                vars.append(n.id)
            else:
                for c in iter_child_nodes(n):
                    collect_loop_vars(c)

        collect_loop_vars(node.target)

        for varn in vars:
            if (isinstance(self.scope.get(varn), Importation)
                    # unused ones will get an unused import warning
                    and self.scope[varn].used):
                self.report(messages.ImportShadowedByLoopVar,
                            node.lineno, varn, self.scope[varn].source.lineno)

        self.handle_children(node)

    def NAME(self, node):
        """
        Locate the name in locals /function / globals scopes.
        """
        import_starred = self.scope.import_starred

        # try local scope
        if self.scope.set_used(node):
            return

        # try enclosing function scopes
        for scope in self.scope_stack[-2:0:-1]:
            import_starred = import_starred or scope.import_starred
            if not isinstance(scope, FunctionScope):
                continue

            if scope.set_used(node):
                return

        # try global scope
        import_starred = import_starred or self.scope_stack[0].import_starred
        if not self.scope_stack[0].set_used(node):
            if not import_starred and not allow_undefined_name(node.id):
                self.report(messages.UndefinedName, node.lineno, node.col_offset, node.id)

    def DELETE(self, node):
        for target in node.targets:
            if isinstance(self.scope, FunctionScope) and target.id in self.scope.globals:
                del self.scope.globals[target.id]
            else:
                self.add_binding(target.lineno, target.col_offset, UnBinding(target.id, target))

    def FUNCTIONDEF(self, node):
        self.handle_nodes(node.decorators)
        self.add_binding(node.lineno, node.col_offset, FunctionDefinition(node.name, node))
        self.LAMBDA(node)

    def LAMBDA(self, node):
        self.handle_nodes(node.args.defaults)

        @self.defer
        def func():
            args = []

            def add_args(arglist):
                for arg in arglist:
                    # handle lambda a, (b, c), d: None
                    if isinstance(arg, _ast.Tuple):
                        add_args(arg.elts)
                    else:
                        if arg.id in args:
                            self.report(messages.DuplicateArgument, arg.lineno, arg.col_offset, arg.id)
                        args.append(arg.id)

    def CLASSDEF(self, node):
        self.add_binding(node.lineno, node.col_offset, Assignment(node.name, node))
        self.handle_nodes(node.bases)

        self.push_class_scope()
        self.handle_nodes(node.body)
        self.pop_scope()

    def ASSIGN(self, node):
        self.handle_node(node.value)

        def assign_nodes(targets):
            for target in targets:
                if isinstance(target, (_ast.Tuple, _ast.List)):
                    yield assign_nodes(target)
                else:
                    yield target

        for target in assign_nodes(node.targets):
            name = target.attr if isinstance(target, _ast.Attribute) else target.id

            # TODO: missing UndefinedLocal message here
            self.add_binding(target.lineno, target.col_offset, Assignment(name, target))

        for target in node.targets:
            self.handle_node(target)

    def IMPORT(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.add_binding(node.lineno, node.col_offset, Importation(name, node))

    def IMPORTFROM(self, node):
        # handle "from __future__ import ..."
        if node.module == '__future__':
            if not self.futures_allowed:
                names = [alias.name for alias in node.names]
                self.report(messages.LateFutureImport, node.lineno, node.col_offset, names)
        else:
            self.futures_allowed = False

        for alias in node.names:
            if alias.name == '*':
                self.scope.import_starred = True
                self.report(messages.ImportStarUsed, node.lineno, node.module)
                continue

            name = alias.asname or alias.name
            importation = Importation(name, node)
            if node.module == '__future__':
                importation.used = (self.scope, node.lineno, node.col_offset)
            self.add_binding(node.lineno, node.col_offset, importation)
