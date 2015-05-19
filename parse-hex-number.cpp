#include <boost/cstdint.hpp>
#include <iostream>
#include <sstream>
#include <string>

boost::int32_t parse_hex(const std::string &str)
{
  std::stringstream ss;
  ss << std::hex << str;
  boost::int32_t ret;
  ss >> ret;
  return ret;
}


int main(int argc, char *argv[])
{
  std::cout << parse_hex("dead") << std::endl;
  std::cout << parse_hex("beef") << std::endl;
  std::cout << parse_hex("10") << std::endl;
}
