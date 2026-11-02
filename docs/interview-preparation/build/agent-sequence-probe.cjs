const fs = require('node:fs');
const path = require('node:path');
// The source project is intentionally not bundled with this handbook.
const sourceRoot = process.env.CODEX_AGENT_SOURCE_ROOT || process.argv[2];
if (!sourceRoot) {
  throw new Error('Set CODEX_AGENT_SOURCE_ROOT (or the first argument) to an authorized source checkout containing server/src/board.js. No SDK or model is called.');
}
const boardPath = path.resolve(sourceRoot, 'server/src/board.js');
if (!fs.existsSync(boardPath)) throw new Error('The supplied source checkout has no server/src/board.js.');
const {DelmBoard} = require(boardPath);

(async()=>{
  const board=new DelmBoard({actors:['A','B']});
  const steps=[];
  function record(action,response){
    const task=board.queueState()[0];
    steps.push({action,logSequence:board.lastSequence,viewSequence:response.view?response.view.sequence:response.sequence,lastReadA:board.lastRead('A'),lastReadB:board.lastRead('B'),state:task.state,owner:task.owner??null,returnedFull:response.view?response.view.full:response.full,wokeBy:response.woke_by??null});
  }
  const pub=board.publish('A',[{subject:'T',detail:'task detail'}]);
  const id=pub.items[0].id;
  record('A publish T',pub);
  record('B first read',await board.read('B'));
  record('A claim T',board.claim('A',id));
  record('B incremental read',await board.read('B'));
  record('A done T',board.done('A',id,'task done',undefined,'complete-T'));
  record('B waiting read',await board.read('B',{waitSeconds:1}));
  const timeout=await board.read('B',{waitSeconds:1});
  const result={steps,timeout:{logSequence:board.lastSequence,viewSequence:timeout.sequence,lastReadB:board.lastRead('B'),wokeBy:timeout.woke_by},events:board.exportEvents().map(e=>({sequence:e.sequence,actor:e.actor,kind:e.kind,via:e.payload.via??null}))};
  fs.writeFileSync(path.join(__dirname,'agent-sequence-probe.json'),JSON.stringify(result,null,2),'utf8');
  console.log(JSON.stringify(result,null,2));
})().catch(e=>{console.error(e);process.exitCode=1;});
