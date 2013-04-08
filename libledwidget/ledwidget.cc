#include <QPainter>
#include <QEvent>
#include "ledwidget.h"

   // QRadialGradient ( const QPointF & center, qreal centerRadius, const QPointF & focalPoint, qreal focalRadius )

LEDWidget::LEDWidget(QWidget *parent)
   : QWidget(parent)
   , m_ledOn(false)
   , m_onColor(Qt::green)
   , m_offColor(Qt::darkGreen)
{
}

LEDWidget::LEDWidget(const QColor &on_color, const QColor &off_color, QWidget *parent)
   : QWidget(parent)
   , m_ledOn(false)
   , m_onColor(on_color)
   , m_offColor(off_color)
{
}

void LEDWidget::paintEvent(QPaintEvent *)
{
   const int side = qMin(width(), height());
   QPainter painter(this);
   painter.setRenderHint(QPainter::Antialiasing);
   painter.translate(width() / 2, height() / 2);
   painter.scale(side / 200.0, side / 200.0);

   QPen pen(isEnabled() ? Qt::black : Qt::darkGray);
   painter.setPen(pen);

   QRadialGradient gradient(QPointF(.0, .0), 100.0, QPointF(20.0, -25.0));
   gradient.setColorAt(0.0, Qt::white);

   if (isEnabled())
      gradient.setColorAt(0.6, m_ledOn ? m_onColor : m_offColor);
   else
      gradient.setColorAt(0.6, Qt::gray);

   QBrush brush(gradient);
   painter.setBrush(brush);

   painter.drawEllipse(QPoint(0, 0), 96, 96);
}

void LEDWidget::changeEvent(QEvent *event)
{
   if (event->type() == QEvent::EnabledChange)
      update();
}

void LEDWidget::setState(bool on)
{
   if (m_ledOn != on) {
      m_ledOn = on;
      update();
      emit stateChanged(on);
      if (on) emit turnedOn();
      else    emit turnedOff();
   }
}

void LEDWidget::setOnColor(const QColor &c)
{
   m_onColor = c;
   update();
}

void LEDWidget::setOffColor(const QColor &c)
{
   m_offColor = c;
   update();
}
