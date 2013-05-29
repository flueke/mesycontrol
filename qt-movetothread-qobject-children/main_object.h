#ifndef UUID_76b71626_62b9_4569_a875_81f05e747667
#define UUID_76b71626_62b9_4569_a875_81f05e747667

#include <QObject>

class MainObject: public QObject
{
   Q_OBJECT
   public:
      MainObject(QObject *parent = 0);
};
#endif
