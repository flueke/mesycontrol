#ifndef UUID_fa45e5e6_7b9b_44c0_88ff_68a6fa55a373
#define UUID_fa45e5e6_7b9b_44c0_88ff_68a6fa55a373

#include <QDesignerCustomWidgetInterface>

class LEDWidgetDesignerPlugin: public QObject, QDesignerCustomWidgetInterface
{
   Q_OBJECT
   Q_INTERFACES(QDesignerCustomWidgetInterface)

   public:
      LEDWidgetDesignerPlugin(QObject *parent = 0);

      bool isContainer() const;
      bool isInitialized() const;
      QIcon icon() const;
      QString domXml() const;
      QString group() const;
      QString includeFile() const;
      QString name() const;
      QString toolTip() const;
      QString whatsThis() const;
      QWidget *createWidget(QWidget *parent);
      void initialize(QDesignerFormEditorInterface *core);

   private:
      bool initialized;
};

#endif
