"""Offline daemon-boundary tests: no containers or real credentials."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from launcher.transport import DockerTransport

MCP='a'*64
GATEWAY='b'*64
IMAGES={name:'sha256:'+char*64 for name,char in [('agent','1'),('evaluator','2'),('mcp','3'),('gateway','4')]}
NETWORK={'Id':'c'*64,'Name':'mcpbench_db','Internal':True,'Driver':'bridge',
         'Labels':{'com.docker.compose.project':'mcpbench','com.docker.compose.network':'db'},'IPAM':{'Config':[{'Subnet':'172.28.0.0/16'}]}}
FRESH={'Id':MCP,'Image':IMAGES['mcp'],'State':{'Running':True,'Status':'running'},
       'NetworkSettings':{'Networks':{'mcpbench_db':{'NetworkID':NETWORK['Id'],'IPAddress':'172.28.0.3'}}}}

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.paths={name:Path(self.tmp.name)/name for name in ('control','mcp-control','mcp-output')}
        for p in self.paths.values():p.mkdir(mode=0o700)
        self.driver=DockerTransport(IMAGES,'/nonexistent/synthetic.pgpass')
        self.commands=[]
    def daemon(self,args,**kwargs):
        self.commands.append(args)
        if args[:2]==['docker','create']:
            value=MCP if args[-1]==IMAGES['mcp'] else GATEWAY
        elif args[:3]==['docker','network','inspect']:value=json.dumps(NETWORK)
        elif args[:2]==['docker','inspect']:
            value=json.dumps({'Running':False,'Status':'exited','ExitCode':0} if args[3]=='{{json .State}}' else FRESH)
        elif args[:2]==['docker','logs']:value='private bounded log'
        else:value=''
        return SimpleNamespace(stdout=value.encode(),stderr=b'')
    def start(self):
        response=SimpleNamespace(status=200,read=lambda n:b'ready\n')
        # MagicMock supplies context protocol without opening sockets.
        with patch('launcher.transport.subprocess.run',side_effect=self.daemon),patch('launcher.transport.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value=response
            self.driver.start_mcp(self.paths,time.monotonic()+2,lambda:None)
    def test_two_services_fixed_binding_receipts_and_shared_close(self):
        self.start()
        creates=[c for c in self.commands if c[:2]==['docker','create']]
        mcp,gateway=creates
        self.assertNotIn('--publish',mcp)
        self.assertEqual(mcp[mcp.index('--network')+1],'mcpbench_db')
        self.assertEqual(gateway[gateway.index('--add-host')+1],'mcp:172.28.0.3')
        self.assertNotIn('--mount',gateway)
        for name,value in [('mcp',MCP),('gateway',GATEWAY)]:
            self.assertEqual(json.loads((self.paths['control']/f'{name}-container.json').read_bytes()),{'container_id':value})
        self.assertIn(['docker','network','connect','mcpbench_front',GATEWAY],self.commands)
        with self.assertRaisesRegex(ValueError,'reuse'):self.driver.start_mcp(self.paths,time.monotonic()+1,lambda:None)
        with patch('launcher.transport.subprocess.run',side_effect=self.daemon):self.driver.close(self.paths,2)
        self.assertEqual([c[-1] for c in self.commands if c[:2]==['docker','rm']],[GATEWAY,MCP])
        self.assertTrue((self.paths['control']/'gateway.stderr').is_file())
        self.assertTrue((self.paths['control']/'mcp.stderr').is_file())
    def test_identity_network_and_ip_rejections(self):
        self.assertEqual(str(self.driver.mcp_address(FRESH,NETWORK,MCP,IMAGES['mcp'])),'172.28.0.3')
        for field in ['Id','Image','running','extra-network','network-id','missing-ip','invalid-ip','outside-ip','owner','internal','name']:
            with self.subTest(field=field):
                f,n=deepcopy(FRESH),deepcopy(NETWORK)
                if field in ['Id','Image']:f[field]='mismatch'
                elif field=='running':f['State']['Running']=False
                elif field=='extra-network':f['NetworkSettings']['Networks']['other']={}
                elif field=='network-id':f['NetworkSettings']['Networks']['mcpbench_db']['NetworkID']='bad'
                elif field=='missing-ip':del f['NetworkSettings']['Networks']['mcpbench_db']['IPAddress']
                elif field=='invalid-ip':f['NetworkSettings']['Networks']['mcpbench_db']['IPAddress']='arbitrary.invalid'
                elif field=='outside-ip':f['NetworkSettings']['Networks']['mcpbench_db']['IPAddress']='192.168.1.10'
                elif field=='owner':n['Labels']={}
                elif field=='internal':n['Internal']=False
                elif field=='name':n['Name']='other'
                with self.assertRaises((ValueError,KeyError)):self.driver.mcp_address(f,n,MCP,IMAGES['mcp'])
    def test_partial_start_never_reused(self):
        with patch('launcher.transport.subprocess.run',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):self.driver.start_mcp(self.paths,time.monotonic()+1,lambda:None)
        with self.assertRaisesRegex(ValueError,'reuse'):self.driver.start_mcp(self.paths,time.monotonic()+1,lambda:None)
    def test_stale_receipt_stops_before_start(self):
        (self.paths['control']/'mcp-container.json').write_text('{}')
        with patch('launcher.transport.subprocess.run',side_effect=self.daemon):
            with self.assertRaises(FileExistsError):self.driver.start_mcp(self.paths,time.monotonic()+1,lambda:None)
        self.assertFalse(any(c[:2]==['docker','start'] for c in self.commands))
    def test_close_failure_preserves_container(self):
        self.driver.service_ids={'gateway':GATEWAY}
        with patch('launcher.transport.subprocess.run',side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):self.driver.close(self.paths,.1)
        self.assertEqual(self.driver.service_ids,{'gateway':GATEWAY})
