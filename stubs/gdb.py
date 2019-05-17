from typing import Optional,Tuple,Any,Union,SupportsInt,List
import abc

COMMAND_DATA : int
SYMBOL_UNDEF_DOMAIN : int
SYMBOL_VAR_DOMAIN : int
SYMBOL_STRUCT_DOMAIN : int
SYMBOL_LABEL_DOMAIN : int
SYMBOL_MODULE_DOMAIN : int
SYMBOL_COMMON_BLOCK_DOMAIN : int
SYMBOL_LOC_REGISTER : int
SYMBOL_LOC_ARG : int
SYMBOL_LOC_REF_ARG : int
SYMBOL_LOC_REGPARM_ADDR : int
SYMBOL_LOC_LOCAL : int
SYMBOL_LOC_TYPEDEF : int
SYMBOL_LOC_BLOCK : int
SYMBOL_LOC_CONST_BYTES : int
SYMBOL_LOC_UNRESOLVED : int
SYMBOL_LOC_OPTIMIZED_OUT : int
SYMBOL_LOC_COMPUTED : int
TYPE_CODE_PTR : int
TYPE_CODE_ARRAY : int
TYPE_CODE_STRUCT : int
TYPE_CODE_UNION : int
TYPE_CODE_ENUM : int
TYPE_CODE_FLAGS : int
TYPE_CODE_FUNC : int
TYPE_CODE_INT : int
TYPE_CODE_FLT : int
TYPE_CODE_VOID : int
TYPE_CODE_SET : int
TYPE_CODE_RANGE : int
TYPE_CODE_STRING : int
TYPE_CODE_BITSTRING : int
TYPE_CODE_ERROR : int
TYPE_CODE_METHOD : int
TYPE_CODE_METHODPTR : int
TYPE_CODE_MEMBERPTR : int
TYPE_CODE_REF : int
TYPE_CODE_RVALUE_REF : int
TYPE_CODE_CHAR : int
TYPE_CODE_BOOL : int
TYPE_CODE_COMPLEX : int
TYPE_CODE_TYPEDEF : int
TYPE_CODE_NAMESPACE : int
TYPE_CODE_DECFLOAT : int
TYPE_CODE_INTERNAL_FUNCTION : int

def string_to_argv(args : str) -> List[str]:
    ...

def lookup_type(typ : str) -> Type:
    ...

def lookup_symbol(name : str, block : Optional[Block] = None, domain: int = 0) -> Tuple[Optional[Symbol], bool]:
    ...

def lookup_global_symbol(name : str, domain: int = 0) -> Optional[Symbol]:
    ...

def parse_and_eval(expr : str) -> Value:
    ...

class Value():
    address : Optional[Value]
    is_optimized_out : bool
    type : Type

    def __init__(self, addr : Union[bool, int, float, str, Value, LazyString]): ...

    def cast(self, typ : Type) -> Value: ...

    def __getitem__(self, idx : Union[str,int,Field]) -> Value: ...

    def __int__(self) -> int: ...
    def __index__(self) -> int: ...
    def __add__(self, arg : Union[int, SupportsInt]) -> Value: ...
    def __and__(self, arg : Union[int, SupportsInt]) -> Value: ...
    def __lshift__(self, arg : Union[int, SupportsInt]) -> Value: ...
    def __rshift__(self, arg : Union[int, SupportsInt]) -> Value: ...

    def string(self, encoding : str = '', errors : str = 'strict', length : int = 0) -> str: ...

    ...

class Field():
    ...

class Type():
    alignof : int
    code : int
    name : Optional[str]
    sizeof : int
    tag : Optional[str]

    def pointer(self) -> Type:
        ...

    def target(self) -> Type:
        ...
    ...

class Target():
    ...

class Block():
    ...

class Symbol():
    section : Any
    def value(self) -> Value: ...
    ...

class Register():
    ...

class MinSymbol():
    ...

class Inferior():
    new_thread : Any
    ...

class Objfile():
    architecture : Architecture
    ...

class Architecture():
    ...

class LazyString():
    ...

class Command():
    def __init__(self, name : str, data : int) -> None: ...
    @abc.abstractmethod
    def invoke(self, argument : str, from_tty : bool) -> None: ...
    ...
