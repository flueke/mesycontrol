#ifndef UUID_4717229a_8874_4046_b356_2fd7240b6c97
#define UUID_4717229a_8874_4046_b356_2fd7240b6c97

#include <QObject>

class ChildObject: public QObject
{
   Q_OBJECT
   public:
      ChildObject(QObject *parent = 0);

      void doSomething();
};

#endif
