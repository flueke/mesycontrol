#ifndef UUID_6df6d8be_2c38_46b4_803d_2615fe17acbf
#define UUID_6df6d8be_2c38_46b4_803d_2615fe17acbf

#include <boost/format.hpp>
#include <string>

namespace mesycontrol
{
  // source: http://stackoverflow.com/a/2417770
  struct character_escaper
  {
    template<typename FindResultT>
      std::string operator()(const FindResultT& Match) const
      {
        std::string s;
        for (typename FindResultT::const_iterator i = Match.begin();
            i != Match.end();
            ++i) {
          s += str(boost::format("\\x%02x") % static_cast<int>(*i));
        }
        return s;
      }
  };
} // ns mesycontrol

#endif
