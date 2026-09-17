#include "mode-string-canonicalizer.h"
#include <stdexcept>
namespace mode_string {
Mode parse(std::string_view s){if(s.empty())throw std::invalid_argument("empty");Mode m{};if(s[0]=='r')m.base=Base::read;else if(s[0]=='w')m.base=Base::write;else if(s[0]=='a')m.base=Base::append;else throw std::invalid_argument("base");unsigned seen=0;for(std::size_t i=1;i<s.size();++i){unsigned bit=0;bool* field=nullptr;switch(s[i]){case '+':bit=1;field=&m.update;break;case 'b':bit=2;field=&m.binary;break;case 'x':bit=4;field=&m.exclusive;break;case 'e':bit=8;field=&m.close_on_exec;break;default:throw std::invalid_argument("modifier");}(void)seen;seen|=bit;*field=true;}if(m.exclusive&&m.base==Base::read)throw std::invalid_argument("exclusive read");return m;}
std::string canonical(const Mode& m){if(m.exclusive&&m.base==Base::read)throw std::invalid_argument("exclusive read");std::string s(1,m.base==Base::read?'r':m.base==Base::write?'w':'a');if(m.update)s+='+';if(m.binary)s+='b';if(m.exclusive)s+='x';if(m.close_on_exec)s+='e';return s;}
}
