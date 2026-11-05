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
    bool is_string(int index) const {
        return index>0 && static_cast<std::size_t>(index)<=values.size() && std::holds_alternative<std::string>(values[index-1]);
    }
    std::int64_t get_integer(int index) const {
        auto value=std::get<std::int64_t>(values.at(index-1));
        values.erase(values.begin()+index-1);return value;
    }
    std::string get_string(int index) const {
        auto value=std::get<std::string>(values.at(index-1));
        values.erase(values.begin()+index-1);return value;
    }
};
int main() {
    try {
        int valid=0;
        for(const std::string expected:{"o","t:1.2/c:2.1"})
            for(const std::string desired:{"o","t:0.3/c:1.1","t:5/c:4"})
                for(std::int64_t target=0;target<3;++target) {
                    Stack stack{{std::int64_t{0x7ff123456780},std::int64_t{6},target,expected,desired}};
                    const auto value=consume_write_arguments(stack);
                    if(value.address!=0x7ff123456780 || value.table!=6 || value.target!=target || value.expected!=expected || value.desired!=desired)
                        throw std::runtime_error("arguments shifted or lost");
                    ++valid;
                }
        for(const auto& values:std::vector<std::vector<std::variant<std::int64_t,std::string>>>{
            {std::int64_t{123},std::int64_t{0},std::int64_t{0},std::string{"o"}},
            {std::int64_t{123},std::int64_t{0},std::string{"1"},std::string{"o"},std::string{"o"}},
            {std::int64_t{123},std::int64_t{0},std::int64_t{0},std::int64_t{0},std::string{"o"}}}) {
            Stack stack{values};bool refused=false;
            try {consume_write_arguments(stack);}catch(const std::runtime_error& e){refused=std::string(e.what())=="invalid_argument_types";}
            if(!refused || stack.values!=values) throw std::runtime_error("bad types were consumed or accepted");
        }
        for(const auto target:std::vector<std::int64_t>{-1,-4}) {
            Stack stack{{std::int64_t{123},std::int64_t{0},target,std::string{"o"},std::string{"o"}}};bool refused=false;
            try {consume_write_arguments(stack);}catch(const std::runtime_error& e){refused=std::string(e.what())=="invalid_selection";}
            if(!refused) throw std::runtime_error("negative target accepted");
        }
        std::cout << "PASS consuming-stack argument regression: " << valid << " valid combinations, missing/wrong types and negative targets\n";
        return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
