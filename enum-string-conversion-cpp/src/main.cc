#include "enums.h"
#include <iostream>

using std::cout;
using std::endl;
using namespace my_enums;

int main()
{
   cout << toString(SI_mm) << endl
      << toString(RefManual) << endl
      << toString(SearchNegative) << endl
      << toString(AccurateDirPositive) << endl
      ;

   SIUnit unit                    = fromString<SIUnit>("mm");
   ReferenceType ref_type         = fromString<ReferenceType>("by_switch");
   SearchDirection search_dir     = fromString<SearchDirection>("search_negative");
   AccurateDirection accurate_dir = fromString<AccurateDirection>("negative");

   cout << unit << endl
      << ref_type << endl
      << search_dir << endl
      << accurate_dir << endl
      ;

   fromString("count", unit);
   cout << unit << endl;
}
