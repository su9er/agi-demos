/**
 * Submit a private skill to the curated review queue (P2-4).
 *
 * Modal with semver + optional note. Submitting writes a row to
 * ``skill_submissions`` with status=pending; admins review it on the
 * dedicated admin page.
 */

import { useEffect, useState } from 'react';

import { useMutation } from '@tanstack/react-query';
import { Input, Modal, Space, Typography, message } from 'antd';

import { curatedSkillAPI } from '@/services/curatedSkillService';

import type { SkillResponse } from '@/types/agent';

const { Text } = Typography;
const { TextArea } = Input;

interface SubmitSkillDialogProps {
  skill: SkillResponse | null;
  open: boolean;
  onClose: () => void;
}

const SEMVER_PATTERN = /^\d+\.\d+\.\d+$/;

export function SubmitSkillDialog({ skill, open, onClose }: SubmitSkillDialogProps) {
  const [semver, setSemver] = useState('0.1.0');
  const [note, setNote] = useState('');

  useEffect(() => {
    if (open) {
      setSemver('0.1.0');
      setNote('');
    }
  }, [open]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!skill) throw new Error('no skill');
      return curatedSkillAPI.submit(skill.id, {
        proposed_semver: semver,
        submission_note: note || null,
      });
    },
    onSuccess: () => {
      message.success('已提交至精选库审核队列');
      onClose();
    },
    onError: (err: Error) => {
      message.error(err.message || 'Submit failed');
    },
  });

  const invalidSemver = !SEMVER_PATTERN.test(semver);

  return (
    <Modal
      title={skill ? `提交 "${skill.name}" 到精选库` : '提交到精选库'}
      open={open}
      onCancel={onClose}
      onOk={() => {
        mutation.mutate();
      }}
      okText="提交"
      okButtonProps={{ disabled: invalidSemver }}
      confirmLoading={mutation.isPending}
    >
      <Space direction="vertical" className="w-full" size="middle">
        <Text type="secondary">
          提交后管理员会审核此 Skill 的内容；通过后将发布到精选库，所有租户都可以 fork。
        </Text>
        <div>
          <Text strong>版本号（semver）</Text>
          <Input
            value={semver}
            onChange={(e) => {
              setSemver(e.target.value);
            }}
            placeholder="0.1.0"
            status={invalidSemver ? 'error' : ''}
          />
          {invalidSemver ? (
            <Text type="danger" className="text-xs">
              格式需为 MAJOR.MINOR.PATCH（例如 1.2.3）
            </Text>
          ) : null}
        </div>
        <div>
          <Text strong>提交备注（可选）</Text>
          <TextArea
            rows={4}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
            }}
            placeholder="为什么这个 Skill 值得加入精选库？"
            maxLength={2000}
            showCount
          />
        </div>
      </Space>
    </Modal>
  );
}

export default SubmitSkillDialog;
