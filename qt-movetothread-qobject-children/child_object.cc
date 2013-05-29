#include "child_object.h"
#include <QDebug>

ChildObject::ChildObject(QObject *parent)
   : QObject(parent)
{}

void ChildObject::doSomething()
{
   qDebug() << __PRETTY_FUNCTION__;
}
