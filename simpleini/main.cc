#define SI_SUPPORT_IOSTREAMS
#include "SimpleIni.h"
#include <fstream>
#include <iostream>

using std::cout;
using std::endl;

typedef CSimpleIni::TNamesDepend EntryList;
typedef CSimpleIni::TKeyVal KeyValueMap;

int main()
{
   std::ifstream in("sample.ini", std::ios::binary);
   CSimpleIni ini;

   if (ini.LoadData(in) < 0) {
      cout << "Could not load sample.ini" << endl;
      return 1;
   }

   EntryList sections;
   ini.GetAllSections(sections);

   for (EntryList::const_iterator it=sections.begin(), end=sections.end(); it!=end; ++it) {
      cout << "Section [" << it->pItem << "]" << endl;
      const KeyValueMap *section(ini.GetSection(it->pItem));

      for (KeyValueMap::const_iterator it2=section->begin(), end2=section->end(); it2!=end2; ++it2) {
         cout << "\t" << it2->first.pItem << "=" << it2->second << endl;
      }

      cout << endl;
   }

   return 0;
}
