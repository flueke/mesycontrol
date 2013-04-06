#ifndef UUID_30be2bd7_d11b_4614_bd8d_d48f89c6a857
#define UUID_30be2bd7_d11b_4614_bd8d_d48f89c6a857

#include <QWidget>

class LEDWidget: public QWidget
{
   Q_OBJECT
   public:
      LEDWidget(QWidget *parent = 0);
      LEDWidget(const QColor &on_color, const QColor &off_color, QWidget *parent = 0);

      bool getState() const { return m_ledOn; }
      QColor getOnColor() const { return m_onColor; }
      QColor getOffColor() const { return m_offColor; }

      Q_PROPERTY(bool state READ getState WRITE setState NOTIFY stateChanged)
      Q_PROPERTY(QColor onColor READ getOnColor WRITE setOnColor)
      Q_PROPERTY(QColor offColor READ getOffColor WRITE setOffColor)

      virtual QSize sizeHint() const { return QSize(16, 16); }
      virtual QSize minimumSizeHint() const { return QSize(12, 12); }

   public slots:
      void toggle() { setState(!getState()); }
      void setOn()  { setState(true); }
      void setOff() { setState(false); }
      void setState(bool on);
      void setOnColor(const QColor &c);
      void setOffColor(const QColor &c);

   signals:
      void turnedOn();
      void turnedOff();
      void stateChanged(bool on);

   protected:
      virtual void paintEvent(QPaintEvent *event);

   private:
      bool m_ledOn;
      QColor m_onColor, m_offColor;
};

#endif
