from .runtime import Runtime
from .string_builtins import resolve
from .type_system import parse_type


def execute_collection_command(parts: list[str], runtime: Runtime) -> None:
    collection_type = parts[0]
    if len(parts) < 3:
        raise SyntaxError(f"Usage: {collection_type} <operation> <variable> [arguments]")
    action, name = parts[1], parts[2]
    variable = runtime.require_var(name)
    if parse_type(variable["type"]).name != collection_type:
        raise TypeError(f"Variable '{name}' is not of type '{collection_type}'.")
    collection = variable["value"]

    if collection_type == "list" and action == "append" and len(parts) == 4:
        value = resolve(parts[3], runtime)
        candidate = [*collection, value]
        runtime.validate_container_mutation(collection, candidate)
        collection.append(value)
        return
    if collection_type == "list" and action == "set" and len(parts) == 5:
        index, value = int(parts[3]), resolve(parts[4], runtime)
        candidate = list(collection)
        candidate[index] = value
        runtime.validate_container_mutation(collection, candidate)
        collection[index] = value
        return
    if collection_type == "list" and action == "get" and len(parts) == 5:
        index, destination = int(parts[3]), parts[4]
        runtime.assign_var(destination, collection[index])
        return
    if collection_type == "list" and action == "len" and len(parts) == 4:
        runtime.assign_var(parts[3], len(collection))
        return
    if collection_type == "dict" and action == "set" and len(parts) == 5:
        key, value = resolve(parts[3], runtime), resolve(parts[4], runtime)
        candidate = {**collection, key: value}
        runtime.validate_container_mutation(collection, candidate)
        collection[key] = value
        return
    if collection_type == "dict" and action == "get" and len(parts) == 5:
        key, destination = resolve(parts[3], runtime), parts[4]
        runtime.assign_var(destination, collection[key])
        return
    if collection_type == "set" and action in ("add", "remove") and len(parts) == 4:
        value = resolve(parts[3], runtime)
        if action == "add":
            runtime.validate_container_mutation(collection, collection | {value})
            collection.add(value)
        else:
            collection.remove(value)
        return
    if collection_type == "tuple" and action == "get" and len(parts) == 5:
        index, destination = int(parts[3]), parts[4]
        runtime.assign_var(destination, collection[index])
        return
    raise SyntaxError(f"Invalid {collection_type} operation or arguments.")
