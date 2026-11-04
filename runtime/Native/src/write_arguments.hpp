#pragma once
#include <cstdint>
#include <stdexcept>

struct WriteArguments {std::uintptr_t address;std::int64_t target,expected,desired;};
template<class Lua> WriteArguments consume_write_arguments(const Lua& lua) {
    for(int index=1;index<=4;++index)
        if(!lua.is_integer(index)) throw std::runtime_error("invalid_argument_types");
    // LuaMadeSimple get_integer removes the selected stack entry.
    WriteArguments out;
    out.address=static_cast<std::uintptr_t>(lua.get_integer(1));
    out.target=lua.get_integer(1);
    out.expected=lua.get_integer(1);
    out.desired=lua.get_integer(1);
    if(out.target<0 || out.target>=4 || out.expected<0 || out.expected>1 || out.desired<0 || out.desired>1)
        throw std::runtime_error("invalid_selection");
    return out;
}
