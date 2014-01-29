#ifndef UUID_32b98f6a_ef04_402a_b967_7afdd6f99f8a
#define UUID_32b98f6a_ef04_402a_b967_7afdd6f99f8a

#include <QGroupBox>

class QLineEdit;

class GroupBox: public QGroupBox
{
   Q_OBJECT
   public:
      GroupBox(const QString &title, QWidget *parent = 0);

      /** Access to the QLineEdit that's used to edit the title.
       * Use this to set custom validators or input masks. The Default
       * validator makes sure the title is not empty. */
      QLineEdit *titleLineEdit()
      { return m_lineEdit; }

      virtual bool eventFilter(QObject *watched, QEvent *event);

   signals:
      void titleEdited(const QString &old_title, const QString &new_title);

   protected:
      virtual void mouseDoubleClickEvent(QMouseEvent *event);
      virtual void mousePressEvent(QMouseEvent *event);

   private slots:
      void lineEdit_returnPressed();

   private:
      QLineEdit *m_lineEdit;
};

#endif
