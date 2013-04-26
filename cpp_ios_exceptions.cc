#include <sstream>
#include <iostream>

using std::cout;
using std::endl;

int main()
{
   int i, j, k;
   std::istringstream in;
   in.exceptions(std::ios_base::badbit | std::ios_base::failbit);

   in.str("1 2");
   in >> i >> j;
   cout << i << " " << j << endl;
   in.clear();

   in.str("1 2 3");
   in >> i >> j >> k;
   cout << i << " " << j << " " << k << endl;
   in.clear();
}
