from typing import Callable

from mypy.plugin import AttributeContext, MethodSigContext, Plugin
from mypy.messages import best_matches, for_function
from mypy.nodes import CallExpr, MemberExpr, TypeInfo, Var
from mypy.types import AnyType, CallableType, FunctionLike,Instance, Type, TypeOfAny


def PRecord_set_hook(ctx: MethodSigContext) -> FunctionLike:
    if isinstance(ctx.context, CallExpr) and isinstance(ctx.type, Instance) \
            and all(kind.is_named() for kind in ctx.context.arg_kinds):
        field_names = ctx.type.type.names
        names = ctx.context.arg_names
        arg_types = []
        for name in names:
            typ = None
            if name in field_names:
                if isinstance(field_names[name].node, Var):
                    typ = field_names[name].node.type
            else:
                matches = best_matches(name, field_names.keys(), 3)
                ctx.api.msg.unexpected_keyword_argument_for_function(for_function(ctx.default_signature), name, ctx.context, matches=matches)

            arg_types.append(typ or AnyType(TypeOfAny.unannotated))
        return CallableType(arg_types, ctx.context.arg_kinds, ctx.context.arg_names, ctx.type, ctx.default_signature.fallback)

    return ctx.default_signature.copy_modified(ret_type=ctx.type)


def PRecord_update_hook(ctx: MethodSigContext) -> FunctionLike:
    return ctx.default_signature.copy_modified(ret_type=ctx.type)


def PMap_attribute_hook(ctx: AttributeContext) -> Type:
    if isinstance(ctx.type, Instance) and ctx.type.type.has_base('pyrsistent.PRecord') \
            and isinstance(ctx.context, MemberExpr):
        if not ctx.type.type.has_readable_member(ctx.context.name):
            ctx.api.msg.has_no_attr(ctx.type, ctx.type, ctx.context.name, ctx.context)
    return ctx.default_attr_type


class MyPlugin(Plugin):
    def get_method_signature_hook(self, fullname: str) -> Callable[[MethodSigContext], FunctionLike] | None:
        if fullname.endswith('.set'):
            fqn = self.lookup_fully_qualified(fullname[:-len('.set')])
            if isinstance(fqn.node, TypeInfo) and fqn.node.has_base('pyrsistent.PRecord'):
                return PRecord_set_hook
        if fullname.endswith('.update'):
            fqn = self.lookup_fully_qualified(fullname[:-len('.update')])
            if isinstance(fqn.node, TypeInfo) and fqn.node.has_base('pyrsistent.typing.PMap'):
                return PRecord_update_hook
        return super().get_method_signature_hook(fullname)
    def get_attribute_hook(self, fullname: str) -> Callable[[AttributeContext], Type] | None:
        if fullname.startswith('pyrsistent.typing.PMap'):
            return PMap_attribute_hook
        return super().get_attribute_hook(fullname)


def plugin(version: str):
    # ignore version argument if the plugin works with all mypy versions.
    return MyPlugin

