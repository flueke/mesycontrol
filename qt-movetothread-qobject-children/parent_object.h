#ifndef UUID_eef7bf1b_7f83_47d7_8170_934186330722
#define UUID_eef7bf1b_7f83_47d7_8170_934186330722

#include <QObject>

class ChildObject;

class ParentObject: public QObject
{
   Q_OBJECT
   public:
      ParentObject(QObject *parent = 0);

   public slots:
      void run();

   private:
      ChildObject *child_object;
};

#endif
