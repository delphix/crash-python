# -*- coding: utf-8 -*-
# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:

import gdb

class CrashArchitecture(object):
    ident = "base-class"
    aliases = None
    def __init__(self):
        pass

    def fetch_register_active(self, thread, register):
        raise NotImplementedError("setup_thread_active not implemented")

    def fetch_register_scheduled(self, thread, register):
        raise NotImplementedError("setup_thread_scheduled not implemented")

    def setup_thread_info(self, thread):
        raise NotImplementedError("setup_thread_info not implemented")

    def fetch_register(self, thread, register):
        if thread.info.active:
            self.fetch_register_active(thread, register)
        else:
            self.fetch_register_scheduled(thread, register)

# This keeps stack traces from continuing into userspace and causing problems.
class KernelFrameFilter(object):
    def __init__(self, address):
        self.name = "KernelFrameFilter"
        self.priority = 100
        self.enabled = True
        self.address = address
        gdb.frame_filters[self.name] = self

    def filter(self, frame_iter):
        return KernelAddressIterator(frame_iter, self.address)

class KernelAddressIterator(object):
    def __init__(self, ii, address):
        self.input_iterator = ii
        self.address = address
        self.elided_names = [ "__schedule", "context_switch" ]

    def __iter__(self):
        return self

    def __next__(self):
        frame = next(self.input_iterator)

        pc = frame.inferior_frame().pc()

        if pc < self.address:
            raise StopIteration

        elided_frame = []

        while pc > self.address:
            name = str(frame.inferior_frame().name())
            if name in self.elided_names:
                elided_frame.append(frame)
            else:
                break
            frame = next(self.input_iterator)
            pc = frame.inferior_frame().pc()

        if len(elided_frame) > 0:
            return KernelFrameDecorator(frame, elided_frame)
        elif pc < self.address:
            raise StopIteration
        else:
            return frame

class KernelFrameDecorator(gdb.FrameDecorator.FrameDecorator):
    def __init__(self, processed_frame, elided_frames):
        super(KernelFrameDecorator, self).__init__(processed_frame)
        self.elided_frames = elided_frames

    def elided(self):
        return self.elided_frames

architectures = {}
def register(arch):
    architectures[arch.ident] = arch
    for ident in arch.aliases:
        architectures[ident] = arch

def get_architecture(archname):
    if archname in architectures:
        return architectures[archname]

    return None
