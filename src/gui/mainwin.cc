#include <QPushButton>
#include <QHBoxLayout>
#include "mainwin.h"

Mainwin::Mainwin(QWidget *parent):
  QWidget(parent)
{
  QHBoxLayout *layout = new QHBoxLayout(this);

  QPushButton *button(new QPushButton("connect"));
  connect(button, SIGNAL(clicked()), this, SLOT(connect_button_clicked()));
  layout->addWidget(button);

  button = new QPushButton("disconnect", this);
  connect(button, SIGNAL(clicked()), &m_tcp_client, SLOT(disconnect()));
  layout->addWidget(button);

  button = new QPushButton("send msg", this);
  connect(button, SIGNAL(clicked()), this, SLOT(send_msg_button_clicked()));
  layout->addWidget(button);

  connect(&m_tcp_client, SIGNAL(connecting()), this, SLOT(is_connecting()));
  connect(&m_tcp_client, SIGNAL(connected()), this, SLOT(is_connected()));
  connect(&m_tcp_client, SIGNAL(disconnected()), this, SLOT(is_disconnected()));
  connect(&m_tcp_client, SIGNAL(client_error(const boost::system::error_code &)),
      this, SLOT(client_error(const boost::system::error_code &)));
  connect(&m_tcp_client, SIGNAL(response_received(const mesycontrol::MessagePtr &, const mesycontrol::MessagePtr &)),
      this, SLOT(response_received(const mesycontrol::MessagePtr &, const mesycontrol::MessagePtr &)));

  connect(this, SIGNAL(queue_message(const mesycontrol::MessagePtr &)),
      &m_tcp_client, SLOT(queue_request(const mesycontrol::MessagePtr &)));

  m_tcp_client.start();
}

void Mainwin::connect_button_clicked()
{
  m_tcp_client.connect("localhost", 23000);
}

void Mainwin::send_msg_button_clicked()
{
  qDebug() << __PRETTY_FUNCTION__;
  for (int i=0; i<256; ++i)
    emit queue_message(mesycontrol::Message::make_read_request(0, 0, i));
}

void Mainwin::response_received(const mesycontrol::MessagePtr &request, const mesycontrol::MessagePtr &response)
{
  qDebug() << __PRETTY_FUNCTION__ << "response type =" << response->type;
}

void Mainwin::is_connecting()
{
  qDebug() << __PRETTY_FUNCTION__;
}

void Mainwin::is_connected()
{
  qDebug() << __PRETTY_FUNCTION__;
}

void Mainwin::is_disconnected()
{
  qDebug() << __PRETTY_FUNCTION__;
}

void Mainwin::client_error(const boost::system::error_code &ec)
{
  qDebug() << __PRETTY_FUNCTION__ << QString::fromStdString(ec.message());
}
