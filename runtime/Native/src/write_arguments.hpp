#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

// Arguments: table address, table index, target index, then the expected and desired compositions as text.
struct WriteArguments {std::uintptr_t address;std::int64_t table,target;std::string expected,desired;};
template<class Lua> WriteArguments consume_write_arguments(const Lua& lua) {
    for(int index=1;index<=3;++index)
        if(!lua.is_integer(index)) throw std::runtime_error("invalid_argument_types");
    for(int index=4;index<=5;++index)
        if(!lua.is_string(index)) throw std::runtime_error("invalid_argument_types");
    // LuaMadeSimple getters remove the selected stack entry.
    WriteArguments out;
    out.address=static_cast<std::uintptr_t>(lua.get_integer(1));
    out.table=lua.get_integer(1);
    out.target=lua.get_integer(1);
    out.expected=std::string(lua.get_string(1));
    out.desired=std::string(lua.get_string(1));
    if(out.table<0 || out.target<0 || out.expected.size()>256 || out.desired.size()>256)
        throw std::runtime_error("invalid_selection");
    return out;
}
