import { useState } from "react";
import { Card, CardContent, Input, Checkbox, Button } from "@heroui/react";
import { Disclosure, DisclosureTrigger, DisclosureContent } from "@heroui/react";
import { useGlmStore } from "@/stores/glm-store";

export function GlmConfigCard() {
  const { apiKey, model, fullContext, setApiKey, setModel, setFullContext } = useGlmStore();
  const [saved, setSaved] = useState(false);

  const save = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <Disclosure>
      <Card className="bg-bg-card border border-accent/20">
        <DisclosureTrigger>
          <div className="section-label cursor-pointer hover:text-accent transition-colors" style={{ padding: "10px 12px 8px" }}>
            GLM 配置（智谱 · 点击展开）
          </div>
        </DisclosureTrigger>
        <DisclosureContent>
          <CardContent className="px-3 pb-3 space-y-2">
            <p className="text-[11px] text-text-muted leading-relaxed">
              浏览器本地保存 Token（localStorage）。勾选「智谱 GLM 摘要」时可随分析一并请求摘要。
            </p>
            <Input type="password" aria-label="智谱 API Key（留空则用服务端 KEY）" placeholder="API Key（留空仅用服务端 KEY）" value={apiKey} onChange={(e) => setApiKey(e.target.value)} className="text-sm" />
            <Input aria-label="GLM 模型名" placeholder="模型名（如 glm-4.7）" value={model} onChange={(e) => setModel(e.target.value)} className="text-sm" />
            <Checkbox aria-label="全量语境（含 K 尾与完整结构字段）" isSelected={fullContext} onChange={() => setFullContext(!fullContext)}>
              全量语境（含 K 尾与完整结构字段）
            </Checkbox>
            <Button size="sm" onPress={save}>
              {saved ? "已保存 ✓" : "保存到本机"}
            </Button>
          </CardContent>
        </DisclosureContent>
      </Card>
    </Disclosure>
  );
}
