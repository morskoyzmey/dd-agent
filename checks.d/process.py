from checks import AgentCheck
import time

class ProcessCheck(AgentCheck):

    def find_pids(self, search_string, psutil, exact_match=True):
        """
        Create a set of pids of selected processes.
        Search for search_string 
        """
        found_process_list = []
        for proc in psutil.process_iter():
            found = False
            for string in search_string:
                if exact_match:
                    try:
                        if proc.name == string:
                            found = True
                    except psutil.NoSuchProcess:
                        self.log.warning('Process disappeared while scanning')
                        pass
                    except psutil.AccessDenied, e:
                        self.log.error('Access denied to %s process' % string)
                        self.log.error('Error: %s' % e)
                        raise
                else:
                    if not found:
                        try:
                            if string in ' '.join(proc.cmdline):
                                found = True
                        except psutil.NoSuchProcess:
                            self.warning('Process disappeared while scanning')
                            pass
                        except psutil.AccessDenied, e:
                            self.log.error('Access denied to %s process' % string)
                            self.log.error('Error: %s' % e)
                            raise
 
                if found or string == 'All':
                    found_process_list.append(proc.pid)
            
        return set(found_process_list)
        
    def get_process_memory_size(self, pids, psutil, extended_metrics=False):
        rss = 0
        vms = 0
        if extended_metrics:
            real = 0
        else:
            real = None
        for pid in set(pids):
            try:
                if extended_metrics:
                    mem = psutil.Process(pid).get_ext_memory_info()
                    real += mem.rss - mem.shared
                else:
                    mem = psutil.Process(pid).get_memory_info()

                rss += mem.rss
                vms += mem.vms
                
            # Skip processes dead in the meantime
            except psutil.NoSuchProcess:
                self.warning('Process %s disappeared while scanning' % pid)
                pass

        #Return value in Byte
        return (rss, vms, real)

    def psutil_older_than_0_6_0(self, psutil):
        return psutil.version_info[1] >= 6
        
    def check(self, instance):
        try:
            import psutil
        except ImportError:
            raise Exception('You need the "ps" package to run this check')

        name = instance.get('name', None)
        exact_match = instance.get('exact_match', True)
        search_string = instance.get('search_string', None)

        if name is None:
            raise KeyError('The "name" of process groups is mandatory')

        if search_string is None:
            raise KeyError('The "search_string" is mandatory')
        
        pids = self.find_pids(search_string, psutil, exact_match=exact_match)

        self.gauge('system.processes.number', len(pids), tags=[name])
        rss, vms, real = self.get_process_memory_size(pids, psutil, 
            extended_metrics=self.psutil_older_than_0_6_0(psutil))
        self.gauge('system.processes.mem.rss', rss, tags=[name])
        self.gauge('system.processes.mem.vms', vms, tags=[name])
        if real is not None:
            self.gauge('system.processes.mem.real', real, tags=[name])
