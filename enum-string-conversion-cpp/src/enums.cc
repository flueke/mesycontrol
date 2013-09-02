#include "enums.h"
#include <boost/bimap.hpp>
#include <boost/assign/list_of.hpp>

using boost::assign::list_of;
using std::string;
using namespace my_enums;

namespace
{
template<typename T> struct Data {};

template<typename T>
struct Lookup
{
   static T fromString(const string &str) { return Data<T>::get().left.at(str); }
   static string toString(const T &t)     { return Data<T>::get().right.at(t); }
};

template<>
struct Data<SIUnit>
{
   typedef boost::bimap<string, SIUnit> map_type;

   static map_type &get()
   {
      static map_type ret = list_of<typename map_type::relation>
         ("mm",    SI_mm)
         ("deg",   SI_deg)
         ("tp",    SI_tp)
         ("count", SI_count)
         ;
      return ret;
   }
};

template<>
struct Data<ReferenceType>
{
   typedef boost::bimap<string, ReferenceType> map_type;
   static map_type &get()
   {
      static map_type ret = list_of<typename map_type::relation>
         ("manual",    RefManual)
         ("by_switch", RefBySwitch)
         ;
      return ret;
   }
};

template<>
struct Data<SearchDirection>
{
   typedef boost::bimap<string, SearchDirection> map_type;
   static map_type &get()
   {
      static map_type ret = list_of<typename map_type::relation>
         ("search_positive", SearchPositive)
         ("search_negative", SearchNegative)
         ;
      return ret;
   }
};

template<>
struct Data<AccurateDirection>
{
   typedef boost::bimap<string, AccurateDirection> map_type;
   static map_type &get()
   {
      static map_type ret = list_of<typename map_type::relation>
         ("both",     AccurateDirBoth)
         ("positive", AccurateDirPositive)
         ("negative", AccurateDirNegative)
         ;
      return ret;
   }
};

} // anon namespace

namespace my_enums
{

string toString(const SIUnit &si_unit)         { return Lookup<SIUnit>::toString(si_unit); }
string toString(const ReferenceType &ref_type) { return Lookup<ReferenceType>::toString(ref_type); }
string toString(const SearchDirection &dir)    { return Lookup<SearchDirection>::toString(dir); }
string toString(const AccurateDirection &dir)  { return Lookup<AccurateDirection>::toString(dir); }

void fromString(const string &str, SIUnit &si_unit)         { si_unit   = Lookup<SIUnit>::fromString(str); }
void fromString(const string &str, ReferenceType &ref_type) { ref_type  = Lookup<ReferenceType>::fromString(str); }
void fromString(const string &str, SearchDirection &dir)    { dir       = Lookup<SearchDirection>::fromString(str); }
void fromString(const string &str, AccurateDirection &dir)  { dir       = Lookup<AccurateDirection>::fromString(str); }

} // namespace my_enums
