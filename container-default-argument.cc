#include <vector>
#include <map>

typedef std::map<int, double> my_map;

class Foo
{
   public:
      void f(const std::vector<int> &v = std::vector<int>());
      //void g(const std::map<int, double> &m = std::map<int, double>());
      void h(const my_map &m = my_map());
};


int main()
{
   Foo foo;
}
