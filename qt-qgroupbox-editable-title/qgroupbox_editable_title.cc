#include "qgroupbox_editable_title.h"
#include <QDebug>
#include <QLineEdit>
#include <QMouseEvent>
#include <QStyleOptionGroupBox>
#include <QRegExpValidator>

GroupBox::GroupBox(const QString &title, QWidget *parent)
   : QGroupBox(title, parent)
   , m_lineEdit(new QLineEdit(this))
{
   connect(m_lineEdit, SIGNAL(returnPressed()), this, SLOT(lineEdit_returnPressed()));
   m_lineEdit->setVisible(false);
   m_lineEdit->installEventFilter(this);
   m_lineEdit->setValidator(new QRegExpValidator(QRegExp(".+"), this));
   /* Setting StrongFocus is needed to make the FocusOut event work in the case
    * of a non-checkable groupbox. Toggling the checkable state at runtime will
    * most likely break this but right now I don't know of a way to intercept
    * setCheckable() calls. */
   setFocusPolicy(Qt::StrongFocus);
}

void GroupBox::mouseDoubleClickEvent(QMouseEvent *event)
{
   QStyleOptionGroupBox style_opt;
   initStyleOption(&style_opt);
   const QStyle::SubControl sub_control(style()->hitTestComplexControl(QStyle::CC_GroupBox,
            &style_opt, event->pos(), this));

   /* If the QGroupBox is not checkable clicking on the title returns
    * SC_GroupBoxCheckBox instead of the expected SC_GroupBoxLabel. */

   if (sub_control == (isCheckable() ? QStyle::SC_GroupBoxLabel : QStyle::SC_GroupBoxCheckBox)) {
      m_lineEdit->move(event->pos());
      m_lineEdit->setText(title());
      m_lineEdit->setFocus(Qt::OtherFocusReason);
      m_lineEdit->selectAll();
      m_lineEdit->show();
   }
}

void GroupBox::lineEdit_returnPressed()
{
   m_lineEdit->setVisible(false);
   if (m_lineEdit->text().size()) { // make sure title is never empty
      const QString old_title(title());
      setTitle(m_lineEdit->text());
      emit titleEdited(old_title, title());
   }
}

void GroupBox::mousePressEvent(QMouseEvent *event)
{
   if (isCheckable()) {
      QStyleOptionGroupBox style_opt;
      initStyleOption(&style_opt);
      const QStyle::SubControl sub_control(style()->hitTestComplexControl(QStyle::CC_GroupBox,
               &style_opt, event->pos(), this));

      // turn off checking via single click on the title
      if (sub_control == QStyle::SC_GroupBoxLabel) return;

      // turn off changing checkstate while the lineedit is visible
      if (sub_control == QStyle::SC_GroupBoxCheckBox && m_lineEdit->isVisible()) return;
   }

   // let the base handle the event
   QGroupBox::mousePressEvent(event);
}

bool GroupBox::eventFilter(QObject *watched, QEvent *event)
{
   if (m_lineEdit->isVisible()
         && watched == m_lineEdit
         && ((event->type() == QEvent::KeyPress
            && static_cast<QKeyEvent *>(event)->key() == Qt::Key_Escape)
         || event->type() == QEvent::FocusOut)) {
      m_lineEdit->setVisible(false);
      return true; // event handled
   }
   return false; // let the event pass through
}
