from .runtime import Runtime
from .string_builtins import resolve


def execute_collection_command(parts: list[str], runtime: Runtime) -> None:
    collection_type = parts[0]
    if len(parts) < 3:
        raise SyntaxError(f"Usage: {collection_type} <operation> <variable> [arguments]")
    action, name = parts[1], parts[2]
    variable = runtime.require_var(name)
    if variable["type"] != collection_type:
        raise TypeError(f"Variable '{name}' is not of type '{collection_type}'.")
    collection = variable["value"]

    if collection_type == "list" and action == "append" and len(parts) == 4:
        collection.append(resolve(parts[3], runtime))
        return
    if collection_type == "list" and action == "get" and len(parts) == 5:
        index, destination = int(parts[3]), parts[4]
        runtime.assign_var(destination, collection[index])
        return
    if collection_type == "list" and action == "len" and len(parts) == 4:
        runtime.assign_var(parts[3], len(collection))
        return
    if collection_type == "dict" and action == "set" and len(parts) == 5:
        collection[resolve(parts[3], runtime)] = resolve(parts[4], runtime)
        return
    if collection_type == "dict" and action == "get" and len(parts) == 5:
        key, destination = resolve(parts[3], runtime), parts[4]
        runtime.assign_var(destination, collection[key])
        return
    if collection_type == "set" and action in ("add", "remove") and len(parts) == 4:
        value = resolve(parts[3], runtime)
        if action == "add":
            collection.add(value)
        else:
            collection.remove(value)
        return
    if collection_type == "tuple" and action == "get" and len(parts) == 5:
        index, destination = int(parts[3]), parts[4]
        runtime.assign_var(destination, collection[index])
        return
    raise SyntaxError(f"Invalid {collection_type} operation or arguments.")
