<template>
  <section class="page-surface">
    <div class="page-heading">
      <div><h1>跨境增长工作流</h1><p>从市场洞察到 Listing 合规审核与沙箱发布。</p></div>
      <el-tag type="warning" effect="plain">Sandbox only</el-tag>
    </div>
    <div class="workflow-toolbar">
      <el-select v-model="productId" filterable placeholder="选择商品"><el-option v-for="item in products" :key="item.product_id" :label="item.name" :value="item.product_id" /></el-select>
      <el-select v-model="platform"><el-option v-for="item in platforms" :key="item" :label="item" :value="item" /></el-select>
      <el-input v-model="keyword" placeholder="目标市场关键词" @keyup.enter="generate" />
      <el-button type="primary" :loading="loading" @click="generate">运行工作流</el-button>
    </div>
    <template v-if="workflow">
      <div class="workflow-summary"><div><span>当前阶段</span><strong>{{ currentStage }}</strong></div><p>{{ nextAction }}</p></div>
      <div class="agent-dag">
        <div v-for="(node, index) in displayDag" :key="node.agent" class="dag-node" :data-status="node.status">
          <span>{{ index + 1 }}</span><strong>{{ agentName(node.agent) }}</strong><small>{{ agentPurpose(node.agent) }}</small><el-tag :type="stageType(node.status)" effect="plain">{{ stageStatus(node.status) }}</el-tag>
        </div>
      </div>
      <div class="content-grid">
        <section class="panel section-panel">
          <div class="section-title"><h2>市场研究</h2><el-tag>{{ workflow.market_research.opportunity_score }} / 100</el-tag></div>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="关键词">{{ workflow.market_research.keyword }}</el-descriptions-item>
            <el-descriptions-item label="价格定位">{{ workflow.market_research.price_position }}</el-descriptions-item>
            <el-descriptions-item label="竞品价格">{{ workflow.market_research.competitor_price }}</el-descriptions-item>
            <el-descriptions-item label="客户信号">{{ workflow.market_research.customer_signals.join(' / ') || '暂无' }}</el-descriptions-item>
          </el-descriptions><p>{{ workflow.market_research.insight }}</p>
        </section>
        <section class="panel section-panel">
          <div class="section-title"><h2>合规审核</h2><el-tag :type="workflow.compliance.status === 'passed' ? 'success' : 'danger'">{{ workflow.compliance.status }}</el-tag></div>
          <p v-if="!workflow.compliance.issues.length">标题长度、绝对化用语和医疗宣称检查均通过。</p>
          <el-alert v-for="issue in workflow.compliance.issues" :key="issue.rule" :title="issue.message" type="error" :closable="false" />
          <div class="tag-list"><el-tag v-for="rule in workflow.compliance.checked_rules" :key="rule" effect="plain">{{ rule }}</el-tag></div>
        </section>
        <section class="panel section-panel wide">
          <div class="section-title"><h2>Listing 草稿</h2><el-tag effect="plain">{{ workflow.platform }}</el-tag></div>
          <h3>{{ workflow.listing.title }}</h3><ul><li v-for="item in workflow.listing.bullet_points" :key="item">{{ item }}</li></ul>
          <div class="tag-list"><el-tag v-for="term in workflow.listing.search_terms" :key="term">{{ term }}</el-tag></div>
        </section>
        <section class="panel section-panel wide approval-bar">
          <div><h2>发布控制</h2><p>高风险发布动作必须人工审批，真实平台不会被调用。</p></div>
          <div v-if="recommendation" class="actions">
            <el-tag :type="recommendation.status === 'approved' ? 'success' : 'warning'">{{ recommendation.status }}</el-tag>
            <el-button v-if="recommendation.status === 'pending'" type="primary" @click="approve">批准发布</el-button>
            <el-button :disabled="recommendation.status !== 'approved'" :loading="publishing" @click="publish">沙箱发布</el-button>
          </div>
          <el-alert v-else title="合规审核未通过，不能创建发布审批。" type="error" :closable="false" />
        </section>
        <section v-if="receipt" class="panel section-panel wide receipt"><div><strong>{{ receipt.external_listing_id }}</strong><span>{{ receipt.platform }} · {{ receipt.environment }}</span></div><el-tag type="success">{{ receipt.status }}</el-tag></section>
      </div>
    </template>
    <el-empty v-else description="选择商品并运行跨境增长工作流" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { ecommerceAPI } from "@/api/client"
const products=ref<any[]>([]), productId=ref(""), platform=ref("Amazon US"), keyword=ref("outdoor lifestyle")
const platforms=["Amazon US","Temu US","Walmart US"], workflow=ref<any>(null), recommendation=ref<any>(null), receipt=ref<any>(null)
const loading=ref(false), publishing=ref(false)
const names:Record<string,string>={market_research:"市场研究 Agent",listing_writer:"Listing 生成 Agent",compliance_reviewer:"合规审核 Agent",human_approval:"人工审批",sandbox_publisher:"沙箱发布 Agent"}
const purposes:Record<string,string>={market_research:"评估市场机会与竞品",listing_writer:"生成标题、卖点和关键词",compliance_reviewer:"检查平台规则与风险用语",human_approval:"确认高风险发布动作",sandbox_publisher:"生成模拟平台回执"}
const agentName=(name:string)=>names[name]||name
const agentPurpose=(name:string)=>purposes[name]||""
const displayDag=computed(()=>workflow.value?.dag.map((node:any)=>{if(node.agent==="human_approval"&&recommendation.value?.status==="approved")return{...node,status:"approved"};if(node.agent==="sandbox_publisher"&&receipt.value)return{...node,status:"published"};if(node.agent==="sandbox_publisher"&&recommendation.value?.status==="approved")return{...node,status:"ready"};return node})||[])
const currentStage=computed(()=>receipt.value?"发布完成":recommendation.value?.status==="approved"?"等待沙箱发布":workflow.value?.compliance.status==="passed"?"等待人工审批":"合规审核未通过")
const nextAction=computed(()=>receipt.value?`已生成模拟商品编号 ${receipt.value.external_listing_id}`:recommendation.value?.status==="approved"?"审批已通过，可以执行沙箱发布。":workflow.value?.compliance.status==="passed"?"检查 Listing 内容后批准发布建议。":"修改 Listing 中的违规内容后重新运行工作流。")
const stageStatus=(status:string)=>({completed:"已完成",passed:"已通过",pending:"待审批",waiting:"等待中",approved:"已批准",ready:"可发布",published:"已发布",blocked:"已阻断"} as Record<string,string>)[status]||status
const stageType=(status:string)=>(["completed","passed","approved","published"].includes(status)?"success":status==="blocked"?"danger":"warning")
async function loadProducts(){products.value=(await ecommerceAPI.products()).data.data;productId.value=products.value[0]?.product_id||""}
async function generate(){if(!productId.value)return;loading.value=true;receipt.value=null;try{const data=(await ecommerceAPI.createGrowthWorkflow(productId.value,platform.value,keyword.value)).data.data;workflow.value=data.workflow;recommendation.value=data.recommendation}catch{ElMessage.error("工作流运行失败")}finally{loading.value=false}}
async function approve(){recommendation.value=(await ecommerceAPI.approveRecommendation(recommendation.value.id,recommendation.value.version,"Listing 合规通过，批准沙箱发布")).data.data;ElMessage.success("审批已通过")}
async function publish(){publishing.value=true;try{const data=(await ecommerceAPI.publishGrowthWorkflow(recommendation.value.id)).data.data;receipt.value=data.receipt;ElMessage.success("沙箱发布完成")}catch{ElMessage.error("发布失败，请确认审批状态")}finally{publishing.value=false}}
onMounted(loadProducts)
</script>

<style scoped>
.workflow-toolbar{display:grid;grid-template-columns:220px 160px minmax(220px,1fr) auto;gap:10px;margin-bottom:18px}.agent-dag{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:18px 0}.dag-node{display:grid;gap:3px;min-height:82px;padding:12px;border:1px solid var(--border);border-top:3px solid #2563eb;background:#fff;border-radius:6px}.dag-node span,.dag-node small{color:var(--ink-muted);font-size:12px}.dag-node[data-status="blocked"]{border-top-color:#dc2626}.dag-node[data-status="pending"],.dag-node[data-status="waiting"]{border-top-color:#d97706}.content-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.section-panel{padding:18px}.section-title,.approval-bar,.receipt{display:flex;align-items:center;justify-content:space-between;gap:16px}.section-panel h2{margin:0;font-size:16px}.section-panel h3{font-size:16px;line-height:1.6}.section-panel li{margin:8px 0;line-height:1.5}.wide{grid-column:1/-1}.tag-list{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.actions{display:flex;align-items:center;gap:10px}.receipt strong,.receipt span{display:block}.receipt span{margin-top:4px;color:var(--ink-muted)}
@media(max-width:900px){.workflow-toolbar{grid-template-columns:1fr}.agent-dag{grid-template-columns:1fr 1fr}.content-grid{grid-template-columns:1fr}.wide{grid-column:auto}.approval-bar{align-items:flex-start;flex-direction:column}}
.workflow-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border-left:4px solid #2563eb;background:#f5f8ff}.workflow-summary span,.workflow-summary strong{display:block}.workflow-summary span{color:var(--ink-muted);font-size:12px}.workflow-summary strong{margin-top:3px}.workflow-summary p{margin:0;color:var(--ink-muted)}.dag-node .el-tag{width:max-content;margin-top:5px}@media(max-width:760px){.workflow-summary{align-items:flex-start;flex-direction:column}}
</style>
