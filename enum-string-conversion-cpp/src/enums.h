#ifndef UUID_8bde18b1_0d9b_44ea_9d81_0af0bf092c96
#define UUID_8bde18b1_0d9b_44ea_9d81_0af0bf092c96

#include <string>

namespace my_enums
{

enum SIUnit {
   SI_mm,
   SI_deg,
   SI_tp,    /// target point
   SI_count  /// motor counts
};

enum ReferenceType {
   RefManual,
   RefBySwitch,
};

enum SearchDirection {
   SearchNegative = -1,
   SearchPositive = +1
};

enum AccurateDirection {
   AccurateDirBoth,
   AccurateDirPositive,
   AccurateDirNegative
};

std::string toString(const SIUnit &si_unit);
std::string toString(const ReferenceType &ref_type);
std::string toString(const SearchDirection &dir);
std::string toString(const AccurateDirection &dir);

void fromString(const std::string &str, SIUnit &si_unit);
void fromString(const std::string &str, ReferenceType &ref_type);
void fromString(const std::string &str, SearchDirection &dir);
void fromString(const std::string &str, AccurateDirection &dir);

/* Calls the 2 argument version. */
template<typename T>
T fromString(const std::string &str)
{
   T ret;
   fromString(str, ret);
   return ret;
}

} // namespace my_enums

#endif
