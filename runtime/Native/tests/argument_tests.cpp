#include "../src/write_arguments.hpp"
#include <iostream>
#include <variant>
#include <vector>
#include <string>

// Models the actual consuming getter in pinned LuaMadeSimple, not a normal
// non-consuming Lua stack read. The native stale-state test exposed this bug.
struct Stack {
    mutable std::vector<std::variant<std::int64_t,std::string>> values;
    bool is_integer(int index) const {
        return index>0 && static_cast<std::size_t>(index)<=values.size() && std::holds_alternative<std::int64_t>(values[index-1]);
    }
    std::int64_t get_integer(int index) const {
        auto value=std::get<std::int64_t>(values.at(index-1));
        values.erase(values.begin()+index-1);return value;
    }
};
int main() {
    try {
        for(std::int64_t target=0;target<4;++target)
            for(std::int64_t expected=0;expected<2;++expected)
                for(std::int64_t desired=0;desired<2;++desired) {
                    Stack stack{{std::int64_t{0x7ff123456780},target,expected,desired}};
                    const auto value=consume_write_arguments(stack);
                    if(value.address!=0x7ff123456780 || value.target!=target || value.expected!=expected || value.desired!=desired || !stack.values.empty())
                        throw std::runtime_error("arguments shifted or lost");
                }
        for(const auto& values:std::vector<std::vector<std::variant<std::int64_t,std::string>>>{
            {std::int64_t{123},std::int64_t{0},std::int64_t{0}},
            {std::int64_t{123},std::int64_t{0},std::string{"1"},std::int64_t{0}}}) {
            Stack stack{values};bool refused=false;
            try {consume_write_arguments(stack);}catch(const std::runtime_error& e){refused=std::string(e.what())=="invalid_argument_types";}
            if(!refused || stack.values!=values) throw std::runtime_error("bad types were consumed or accepted");
        }
        for(const auto target:std::vector<std::int64_t>{-1,4,100}) {
            Stack stack{{std::int64_t{123},target,std::int64_t{0},std::int64_t{1}}};bool refused=false;
            try {consume_write_arguments(stack);}catch(const std::runtime_error& e){refused=std::string(e.what())=="invalid_selection";}
            if(!refused) throw std::runtime_error("unowned target accepted");
        }
        std::cout << "PASS consuming-stack argument regression:16 valid combinations, missing/string types and out-of-scope targets\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
