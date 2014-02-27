#ifndef UUID_ca182066_69f1_4416_9021_205d2f05b7dd
#define UUID_ca182066_69f1_4416_9021_205d2f05b7dd

#include <QWidget>
#include <QDebug>
#include "qt_tcp_client.h"

class Mainwin: public QWidget
{
  Q_OBJECT
  public:
    Mainwin(QWidget *parent = 0);

  signals:
    void queue_message(const mesycontrol::MessagePtr &msg);

  public slots:
    void response_received(const mesycontrol::MessagePtr &request, const mesycontrol::MessagePtr &response);

  private slots:
    void connect_button_clicked();
    void send_msg_button_clicked();
    void is_connecting();
    void is_connected();
    void is_disconnected();
    void client_error(const boost::system::error_code &ec);

  private:
    mesycontrol::QtTCPClient m_tcp_client;
};

#endif
