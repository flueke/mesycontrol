#include "main_object.h"
#include "parent_object.h"
#include <QThread>
#include <QTimer>

MainObject::MainObject(QObject *parent)
   : QObject(parent)
{
   ParentObject *parent_object(new ParentObject);
   QThread *thread(new QThread(this));
   parent_object->moveToThread(thread);

   connect(thread, SIGNAL(started()), parent_object, SLOT(run()));
   QTimer::singleShot(0, thread, SLOT(start()));
}
