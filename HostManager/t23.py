import multiprocessing
import time
class Test:
    def __init__(self):
        self.pool = multiprocessing.Pool()
        # self.queue = multiprocessing.Queue()
        m = multiprocessing.Manager()
        self.queue = m.Queue()
    def subprocess(self):
        for i in range(10):
            print("Running")
            time.sleep(1)
            print("Subprocess Completed")
    def start(self):
        self.pool.apply_async(func=self.subprocess)
        print("Subprocess has been started")
        self.pool.close()
        self.pool.join()
    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['pool']
        return self_dict
    def __setstate__(self, state):
        self.__dict__.update(state)

if __name__ == '__main__':
    test = Test()
    test.start()
