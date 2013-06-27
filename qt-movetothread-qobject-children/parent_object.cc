#include "parent_object.h"
#include "child_object.h"
#include <QDebug>

ParentObject::ParentObject(QObject *parent)
   : QObject(parent)
   , child_object(new ChildObject)
{
}

void ParentObject::run()
{
   qDebug() << __PRETTY_FUNCTION__;
   child_object->doSomething();
}
