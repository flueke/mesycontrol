from mesycontrol.script import get_script_context

with get_script_context() as ctx:
    mrc = ctx.make_mrc("mc://localhost:23000")
    print(mrc)
    mrc.connectMrc()
    print(mrc)
